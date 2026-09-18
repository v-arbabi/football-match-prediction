"""
XGBoost, evaluated on the exact same splits as the logistic model
(models/common.py): a season-holdout split (headline result) plus a
walk-forward, multi-roll split restricted to the seasons before the
held-out one (robustness check). The original xgboost_model.py had the
right idea (time-based split, calibration, decile/precision-at-K
reporting) but used a single 80/20 split, and never a season holdout,
which meant the two models were never actually compared on equal
footing. This version fixes that; the model hyperparameters are
otherwise the ones already tuned in the original script.

Run: python models/xgboost_model.py [btts|over25]
"""
import sys
import os
import json
import warnings
from xgboost import XGBClassifier

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from src.config import TRAINING_TABLE_CSV, RESULTS_DIR
from models.common import (
    load_training_table, build_xy, make_season_holdout_split, make_time_slices_by_date,
    score, summarize_rolls, calibrate_prefit,
)

warnings.filterwarnings("ignore")


def compute_scale_pos_weight(y):
    pos, neg = (y == 1).sum(), (y == 0).sum()
    return max(1.0, neg / max(pos, 1))


def build_model(scale_pos_weight):
    return XGBClassifier(
        objective="binary:logistic",
        n_estimators=40,
        learning_rate=0.05,
        max_depth=2,
        min_child_weight=15,
        subsample=0.95,
        colsample_bytree=1.0,
        reg_lambda=10.0,
        reg_alpha=1.0,
        random_state=42,
        scale_pos_weight=scale_pos_weight,
        eval_metric="auc",
        tree_method="hist",
        n_jobs=-1,
    )


def _fit_eval(X_tr, y_tr, X_cal, y_cal, X_te, y_te):
    zero_var = [c for c in X_tr.columns if X_tr[c].nunique() <= 2]
    X_tr = X_tr.drop(columns=zero_var)
    X_cal = X_cal.drop(columns=zero_var, errors="ignore")
    X_te = X_te.drop(columns=zero_var, errors="ignore")

    xgb = build_model(compute_scale_pos_weight(y_tr))
    xgb.fit(X_tr, y_tr)
    calibrated = calibrate_prefit(xgb, X_cal, y_cal)
    prob = calibrated.predict_proba(X_te)[:, 1]
    return score(y_te.to_numpy(), prob)


def run(target: str):
    df = load_training_table(TRAINING_TABLE_CSV)
    X, y = build_xy(df, target)

    # --- headline result: season holdout ---
    split = make_season_holdout_split(df)
    print(f"[xgboost/{target}] season holdout: train {split['train_dates']} | "
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
    print(f"[xgboost/{target}] {len(slices)} walk-forward rolls on the training pool")

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
        "model": "xgboost",
        "target": target,
        "season_holdout": season_holdout,
        "walk_forward": {"per_roll": per_roll, "summary": summarize_rolls(per_roll)} if per_roll else None,
    }
    out_path = os.path.join(RESULTS_DIR, f"xgboost_{target}.json")
    with open(out_path, "w") as f:
        json.dump(result, f, indent=2)
    print(f"[xgboost/{target}] season-holdout AUC={season_holdout['auc']:.3f}  -> {out_path}")
    return result


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "btts"
    run(target)
