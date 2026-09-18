"""
Central paths for the project, all relative to this file so the project
runs the same on any machine. Nothing else in the codebase should
hardcode a path - import from here instead.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_PROCESSED_DIR = os.path.join(PROJECT_ROOT, "data", "processed")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "results")
TRAINING_TABLE_CSV = os.path.join(DATA_PROCESSED_DIR, "training_table.csv")

os.makedirs(RESULTS_DIR, exist_ok=True)
