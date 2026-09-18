"""
Shared pieces for both models (logistic regression and XGBoost), so they
get evaluated on exactly the same splits and the same metrics. Having
this in one place is what makes a "logistic vs XGBoost" comparison fair -
before this was split out, each model script rolled its own train/test
logic, and a couple of them used a random split instead of a time-based
one, which doesn't work for match data where nearby fixtures share
overlapping rolling-form inputs.

Two splits live here:
- make_season_holdout_split: the headline evaluation. The last season of
  each league is held out for testing only and never seen during
  training or calibration - the standard, stricter way to backtest a
  season-by-season model.
- make_time_slices_by_date: a walk-forward, multi-roll split used as a
  secondary robustness check on the training pool only (i.e. restricted
  to seasons before the held-out one), so the headline result isn't
  resting on a single lucky split. Carried over almost unchanged from the
  original logistic_model.py, which already had this part right.
"""
import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score, brier_score_loss, log_loss
from sklearn.calibration import CalibratedClassifierCV

try:
    from sklearn.frozen import FrozenEstimator
    _HAS_FROZEN = True
except Exception:
    _HAS_FROZEN = False


def calibrate_prefit(fitted_model, X_cal, y_cal, method="sigmoid"):
    """
    Wrap an already-fitted model in sigmoid (Platt) calibration, fit only
    on the held-out calibration slice. sklearn changed how you tell
    CalibratedClassifierCV "this model is already fit, just calibrate it"
    a couple of times across versions (cv="prefit" -> FrozenEstimator), so
    this tries the current API first and falls back for older sklearn.
    """
    if _HAS_FROZEN:
        cal = CalibratedClassifierCV(estimator=FrozenEstimator(fitted_model), method=method)
    else:
        try:
            cal = CalibratedClassifierCV(estimator=fitted_model, method=method, cv="prefit")
        except TypeError:
            cal = CalibratedClassifierCV(base_estimator=fitted_model, method=method, cv="prefit")
    cal.fit(X_cal, y_cal)
    return cal

META_COLS = [
    "row_key", "match_id", "league", "season", "date", "time_GMT",
    "home_team_id", "home_team_name", "away_team_id", "away_team_name",
    "home_goals", "away_goals", "btts", "over25", "home_not_win",
]


def load_training_table(csv_path: str) -> pd.DataFrame:
    df = pd.read_csv(csv_path)
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d", errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)
    return df


def build_xy(df: pd.DataFrame, target: str):
    other_target = "over25" if target == "btts" else "btts"
    drop_cols = [c for c in META_COLS if c in df.columns] + [other_target]
    y = df[target].astype(int)
    X = (
        df.drop(columns=[c for c in drop_cols if c in df.columns], errors="ignore")
        .apply(pd.to_numeric, errors="coerce")
        .fillna(0.0)
        .astype(np.float64)
    )
    return X, y


def make_time_slices_by_date(df_sorted, date_col="date",
                              train_frac=0.60, val_frac=0.15, test_frac=0.15,
                              n_rolls=5, step_frac=0.05):
    """
    Expanding-window, walk-forward split by calendar date. Each roll's
    train/val/test windows are contiguous blocks of unique match dates,
    always in chronological order (train dates < val dates < test dates),
    and the whole window slides forward by step_frac between rolls. This
    is what keeps the split honest for time-series data: a model is never
    evaluated on a match that happened before matches it was trained on.
    """
    dates = np.array(sorted(df_sorted[date_col].dt.normalize().unique()))
    m = len(dates)
    base_train = int(np.floor(train_frac * m))
    base_val = int(np.floor(val_frac * m))
    base_test = int(np.floor(test_frac * m))
    step = max(1, int(round(step_frac * m)))
    free = m - (base_train + base_val + base_test)
    max_rolls = 1 + (free // step) if free >= 0 else 1
    rolls = min(n_rolls, max_rolls)

    slices = []
    dn = df_sorted[date_col].dt.normalize()
    for r in range(rolls):
        train_end = base_train + r * step
        val_end = train_end + base_val
        test_end = val_end + base_test
        if test_end > m:
            continue
        train_idx = df_sorted.index[dn.isin(dates[:train_end])]
        val_idx = df_sorted.index[dn.isin(dates[train_end:val_end])]
        test_idx = df_sorted.index[dn.isin(dates[val_end:test_end])]
        slices.append({
            "roll": r + 1,
            "train_idx": train_idx, "val_idx": val_idx, "test_idx": test_idx,
            "train_dates": (str(pd.Timestamp(dates[0]).date()), str(pd.Timestamp(dates[train_end - 1]).date())),
            "test_dates": (str(pd.Timestamp(dates[val_end]).date()), str(pd.Timestamp(dates[test_end - 1]).date())),
        })
    return slices


def make_season_holdout_split(df, league_col="league", season_col="season",
                               date_col="date", cal_frac=0.15):
    """
    The stricter split, and the one the headline results are reported on:
    for each league, its single most recent season is held out as a test
    set and never touched during training or calibration - not even
    indirectly through a rolling window that crosses the season boundary,
    since the feature pipeline only ever looks backward in time. Everything
    from earlier seasons is the training pool; a chronological slice off
    the *end* of that pool (cal_frac, by date - not a random sample) is
    used only to fit the probability calibration, never the model itself.

    This is a single, fixed split rather than a rolling one, which is
    exactly the point: it mirrors how the model would actually be used
    (train on everything you have, deploy on next season) rather than
    letting a favorable random split flatter the result.
    """
    df = df.sort_values(date_col).reset_index(drop=True)
    last_season = df.groupby(league_col)[season_col].transform("max")
    test_mask = df[season_col] == last_season
    test_idx = df.index[test_mask]

    pool_idx = df.index[~test_mask]
    pool_sorted = df.loc[pool_idx].sort_values(date_col).index
    n_cal = max(1, int(round(cal_frac * len(pool_sorted))))
    cal_idx = pool_sorted[-n_cal:]
    train_idx = pool_sorted[:-n_cal]

    held_out_seasons = sorted(df.loc[test_idx, season_col].unique().tolist())

    return {
        "train_idx": train_idx,
        "cal_idx": cal_idx,
        "test_idx": test_idx,
        "held_out_seasons": held_out_seasons,
        "train_dates": (str(df.loc[train_idx, date_col].min().date()),
                         str(df.loc[train_idx, date_col].max().date())),
        "test_dates": (str(df.loc[test_idx, date_col].min().date()),
                        str(df.loc[test_idx, date_col].max().date())),
    }


def precision_at_pct(y_true, prob, pct):
    n = len(prob)
    k = max(1, int(round(pct * n)))
    idx = np.argsort(-prob)[:k]
    return float(pd.Series(y_true).iloc[idx].mean())


def score(y_true, prob):
    return {
        "auc": float(roc_auc_score(y_true, prob)),
        "brier": float(brier_score_loss(y_true, prob)),
        "logloss": float(log_loss(y_true, prob, labels=[0, 1])),
        "precision_at_top20pct": precision_at_pct(y_true, prob, 0.20),
        "base_rate": float(np.mean(y_true)),
        "n": int(len(y_true)),
    }


def summarize_rolls(per_roll_scores):
    aucs = [s["auc"] for s in per_roll_scores]
    briers = [s["brier"] for s in per_roll_scores]
    return {
        "auc_mean": float(np.mean(aucs)), "auc_min": float(np.min(aucs)), "auc_max": float(np.max(aucs)),
        "brier_mean": float(np.mean(briers)),
        "n_rolls": len(per_roll_scores),
    }
