#!/usr/bin/env python3
"""
One-command entry point: trains and evaluates both models (logistic,
XGBoost) on both targets (BTTS, Over 2.5) and prints a summary table.
This is the fastest way to reproduce the results reported in README.md -
everything else in src/ and scraper/ is provenance for how
data/processed/training_table.csv was built, not something you need to
re-run to see the results.

Usage:
    python run.py                 # train + evaluate all 4 model/target combos
    python run.py --rebuild-data  # also rebuild training_table.csv first,
                                   # from data/raw/fbref/ (needs a fuller
                                   # local raw dataset than the 2 sample
                                   # files that ship here - see data/README.md;
                                   # against just the samples this step will
                                   # correctly produce zero rows and stop)
"""
import argparse

from models import logistic, xgboost_model

MODELS = (("logistic", logistic), ("xgboost", xgboost_model))
TARGETS = ("btts", "over25")


def rebuild_training_table():
    from src.build_dataset import main as build_main
    print("[run] rebuilding data/processed/training_table.csv from data/raw/fbref/ ...")
    build_main()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rebuild-data", action="store_true",
                         help="rebuild training_table.csv from data/raw/fbref/ before training")
    args = parser.parse_args()

    if args.rebuild_data:
        rebuild_training_table()

    rows = []
    for target in TARGETS:
        for name, module in MODELS:
            print(f"\n=== {name} / {target} ===")
            result = module.run(target)
            sh = result["season_holdout"]
            rows.append((name, target, sh["auc"], sh["brier"], sh["held_out_seasons"]))

    print("\n" + "=" * 64)
    print("Season-holdout results (last season per league, test-only):")
    print(f"{'model':<12}{'target':<10}{'AUC':>8}{'Brier':>8}   held-out season(s)")
    for name, target, auc, brier, seasons in rows:
        print(f"{name:<12}{target:<10}{auc:>8.3f}{brier:>8.3f}   {seasons}")
    print("=" * 64)
    print("Full per-roll numbers (incl. walk-forward robustness check): results/<model>_<target>.json")


if __name__ == "__main__":
    main()
