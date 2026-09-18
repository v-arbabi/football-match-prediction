"""
Two figures that go with the results in README.md:

1. results_comparison.png - season-holdout AUC for all four model/target
   combinations against the 0.50 chance line, with the walk-forward
   min-max range drawn on top of each bar so it's clear how much a
   single holdout season's number moves around.
2. feature_signal.png - the absolute correlation between every rolling
   "combo" feature and its target, for both targets. This is the actual
   reason the models don't do much: the inputs themselves barely relate
   to the outcome, so no amount of tuning was going to fix it.

Run: python analysis/plot_results.py
Reads: results/*.json, data/processed/training_table.csv
Writes: analysis/results_comparison.png, analysis/feature_signal.png
"""
import json
import os

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
RESULTS_DIR = os.path.join(ROOT, "results")
TRAINING_TABLE = os.path.join(ROOT, "data", "processed", "training_table.csv")

MODELS = ["logistic", "xgboost"]
MODEL_LABELS = {"logistic": "Logistic (elasticnet)", "xgboost": "XGBoost"}
TARGETS = ["btts", "over25"]
TARGET_LABELS = {"btts": "BTTS", "over25": "Over 2.5"}


def load_result(model, target):
    with open(os.path.join(RESULTS_DIR, f"{model}_{target}.json")) as f:
        return json.load(f)


def plot_results_comparison():
    fig, ax = plt.subplots(figsize=(7, 4.5))

    bar_width = 0.35
    x = range(len(TARGETS))

    for i, model in enumerate(MODELS):
        aucs, err_low, err_high = [], [], []
        for target in TARGETS:
            r = load_result(model, target)
            sh_auc = r["season_holdout"]["auc"]
            wf = r["walk_forward"]["summary"] if r.get("walk_forward") else None
            aucs.append(sh_auc)
            if wf:
                err_low.append(max(0, sh_auc - wf["auc_min"]))
                err_high.append(max(0, wf["auc_max"] - sh_auc))
            else:
                err_low.append(0)
                err_high.append(0)

        offset = (i - 0.5) * bar_width
        positions = [xi + offset for xi in x]
        ax.bar(positions, aucs, bar_width, label=MODEL_LABELS[model],
               yerr=[err_low, err_high], capsize=4, alpha=0.85)

    ax.axhline(0.50, color="black", linestyle="--", linewidth=1, label="chance (0.50)")
    ax.set_xticks(list(x))
    ax.set_xticklabels([TARGET_LABELS[t] for t in TARGETS])
    ax.set_ylabel("AUC")
    ax.set_ylim(0.35, 0.65)
    ax.set_title("Season-holdout AUC by model and target\n(error bars: walk-forward min-max on earlier seasons)")
    ax.legend(loc="upper right", fontsize=9)
    fig.tight_layout()

    out_path = os.path.join(HERE, "results_comparison.png")
    fig.savefig(out_path, dpi=150)
    print(f"[plot_results] wrote {out_path}")


def plot_feature_signal():
    df = pd.read_csv(TRAINING_TABLE)
    feat_cols = [c for c in df.columns if c.startswith("w5_combo_")]

    fig, axes = plt.subplots(1, 2, figsize=(11, 6), sharex=True)

    for ax, target in zip(axes, TARGETS):
        corr = df[feat_cols].corrwith(df[target]).abs().sort_values(ascending=False).head(15)
        labels = [c.replace("w5_combo_", "") for c in corr.index]
        ax.barh(labels[::-1], corr.values[::-1], color="#4C72B0")
        ax.set_title(TARGET_LABELS[target])
        ax.set_xlabel("|Pearson r|")
        ax.set_xlim(0, 0.35)

    fig.suptitle("Even the single best 5-match rolling feature barely moves with the outcome")
    fig.tight_layout(rect=[0, 0, 1, 0.96])

    out_path = os.path.join(HERE, "feature_signal.png")
    fig.savefig(out_path, dpi=150)
    print(f"[plot_results] wrote {out_path}")


if __name__ == "__main__":
    plot_results_comparison()
    plot_feature_signal()
