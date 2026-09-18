# Data

```
raw/fbref/<league>/<season>/<match_id>_fbref_<league>_<season>_<home>_<away>.json
match_lists/fbref/<league>/fbref_<league>_<season>.json
processed/training_table.csv
```

This mirrors the real folder layout - one directory per league, one
subdirectory per season - but almost all of it is empty on purpose. The
full scraped dataset is about 11 GB (eight leagues, several seasons each)
and isn't included here; what's included is:

- **`raw/fbref/premier_league/2023_2024/`** - 2 real sample match files,
  so the raw JSON shape is visible (`meta_data` / `home` / `away`, each
  side's box-score stats under `team_stat`).
- **`match_lists/fbref/premier_league/`** - 1 real sample fixture-list
  file (one season's fixtures, keyed by match ID, with each match's
  FBref link).
- **`processed/training_table.csv`** - the full, real feature table
  (2,157 matches, 2018-19 through 2023-24) that the models in `models/`
  actually train and evaluate on. This is the only data file that
  matters for reproducing the reported results.

The other seven league folders are empty placeholders showing where their
data would sit. `src/build_dataset_by_matches.py` discovers whatever
league/season folders actually contain `.json` files, so pointing it at a
full local copy of the raw data - with the same folder names - rebuilds
`training_table.csv` without any code changes.
