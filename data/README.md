@"
# Data

raw/fbref/<league>/<season>/<match_id>fbref<league><season><home><away>.json
match_lists/fbref/<league>/fbref<league>_<season>.json
processed/training_table.csv


This mirrors the real folder layout - one directory per league, one
subdirectory per season - but almost all of it is empty on purpose. The
full scraped dataset is about 11 GB and isn't included here; what's
included is:

- **``raw/fbref/<league>/<season>/``** - one real sample match file per
  season folder, for every league/season actually scraped: Bundesliga,
  La Liga, Ligue 1, Premier League (2017-18 through 2024-25), Eredivisie
  and Primeira Liga (2018-19 through 2024-25), and Serie A (2024-25
  only) - 47 sample files total, so the raw JSON shape is visible for
  every league (``meta_data`` / ``home`` / ``away``, each side's
  box-score stats under ``team_stat``). Belgian Pro League has no raw
  match files here at all (see below).
- **``match_lists/fbref/premier_league/``** - 1 real sample fixture-list
  file (one season's fixtures, keyed by match ID, with each match's
  FBref link). The other leagues' ``match_lists/`` folders are empty
  placeholders.
- **``processed/training_table.csv``** - the full, real feature table
  (8,116 matches, 2017-18 through 2024-25, eight leagues) that the
  models in ``models/`` actually train and evaluate on. Two of those
  eight leagues (Belgian Pro League, Serie A) only have one season each
  in this table and get filtered out automatically before training -
  see the Results section of the main README - so the reported results
  reflect six leagues, 7,916 matches. This is the only data file that
  matters for reproducing the reported results.

Everything else under ``raw/`` and ``match_lists/`` - and the Belgian
Pro League folder entirely - is an empty placeholder showing where the
full data would sit. ``src/build_dataset_by_matches.py`` discovers
whatever league/season folders actually contain ``.json`` files, so
pointing it at a full local copy of the raw data - with the same folder
names - rebuilds ``training_table.csv`` without any code changes.
"@ | Out-File -Encoding utf8 data\README.md
````