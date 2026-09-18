"""
Shared paths for both the scraper and the feature pipeline. Everything
is relative to this file so the project runs the same on any machine.
"""
import os

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")

RAW_MATCH_DIR = os.path.join(DATA_DIR, "raw")
FBREF_RAW_MATCH = os.path.join(RAW_MATCH_DIR, "fbref")

MATCH_LIST_DIR = os.path.join(DATA_DIR, "match_lists")
FBREF_MATCH_LIST_DIR = os.path.join(MATCH_LIST_DIR, "fbref")

PROCESSED_DIR = os.path.join(DATA_DIR, "processed")
