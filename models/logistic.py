"""
Elasticnet-penalized logistic regression. Evaluated two ways (see
models/common.py): a season-holdout split (the headline result - last
season per league held out for testing only) and a walk-forward,
multi-roll split restricted to the seasons before the held-out one (a
secondary robustness check). This is the model script the project's
methodology was actually right on from early on - carried over from the
original logistic_model.py with the split/eval code factored out to
models/common.py so XGBoost gets evaluated the exact same way.

Run: python models/logistic.py [btts|over25]
"""
import sys
import os
import json
import warnings
import numpy as np
from sklearn.preprocessing import StandardScaler
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import TRAINING_TABLE_CSV, RESULTS_DIR
from models.common import (
    load_training_table, build_xy, make_season_holdout_split, make_time_slices_by_date,
    score, summarize_rolls, calibrate_prefit,
)

warnings.filterwarnings("ignore")


def build_model():
    return Pipeline(steps=[
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(
            solver="saga", penalty="elasticnet", l1_ratio=0.2, C=0.01,
            class_weight="balanced", max_iter=15000, random_state=42,
        )),
    ])


def drop_high_correlation(X, thresh=0.95):
    if X.shape[1] < 2:
        return X
    corr = X.corr().abs()
    upper = corr.where(np.triu(np.ones(corr.shape), k=1).astype(bool))
    to_drop = [c for c in upper.columns if any(upper[c] > thresh)]
    return X.drop(columns=to_drop)


def _fit_eval(X_tr, y_tr, X_cal, y_cal, X_te, y_te, corr_prune=True):
    zero_var = [c for c in X_tr.columns if X_tr[c].nunique() <= 1]
    X_tr = X_tr.drop(columns=zero_var)
    if corr_prune:
        X_tr = drop_high_correlation(X_tr)
    keep = X_tr.columns
    X_cal, X_te = X_cal[keep], X_te[keep]

    model = build_model().fit(X_tr, y_tr)
    calibrated = calibrate_prefit(model, X_cal, y_cal)
    prob = calibrated.predict_proba(X_te)[:, 1]
    return score(y_te.to_numpy(), prob)


def run(target: str):
    df = load_training_table(TRAINING_TABLE_CSV)
    X, y = build_xy(df, target)

    # --- headline result: season holdout ---
    split = make_season_holdout_split(df)
    print(f"[logistic/{target}] season holdout: train {split['train_dates']} | "
          f"held-out season(s) {split['held_out_seasons']} {split['test_dates']}")

    season_holdout = _fit_eval(
        X.loc[split["train_idx"]], y.loc[split["train_idx"]],
        X.loc[split["cal_idx"]], y.loc[split["cal_idx"]],
        X.loc[split["test_idx"]], y.loc[split["test_idx"]],
    )
    season_holdout["held_out_seasons"] = split["held_out_seasons"]
    print(f"  season holdout: AUC={season_holdout['auc']:.3f}  Brier={season_holdout['brier']:.3f}  n={season_holdout['n']}")

    # --- secondary robustness check: walk-forward, restricted to the ---
    # --- training pool only (seasons before the held-out one)        ---
    train_pool_df = df.loc[split["train_idx"].union(split["cal_idx"])].sort_values("date")
    slices = make_time_slices_by_date(train_pool_df)
    print(f"[logistic/{target}] {len(slices)} walk-forward rolls on the training pool")

    per_roll = []
    for sl in slices:
        s = _fit_eval(
            X.loc[sl["train_idx"]], y.loc[sl["train_idx"]],
            X.loc[sl["val_idx"]], y.loc[sl["val_idx"]],
            X.loc[sl["test_idx"]], y.loc[sl["test_idx"]],
        )
        s["roll"] = sl["roll"]
        s["test_dates"] = sl["test_dates"]
        per_roll.append(s)
        print(f"  roll {sl['roll']}: test {sl['test_dates']}  AUC={s['auc']:.3f}  Brier={s['brier']:.3f}  n={s['n']}")

    result = {
        "model": "logistic_elasticnet",
        "target": target,
        "season_holdout": season_holdout,
        "walk_forward": {"per_roll": per_roll, "summary": summarize_rolls(per_roll)} if per_roll else None,
    }
    out_path = os.path.join(RESULTS_DIR, f"logistic_{target}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[logistic/{target}] season-holdout AUC={season_holdout['auc']:.3f}  -> {out_path}")
    return result


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "btts"
    run(target)
