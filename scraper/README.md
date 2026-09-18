# Scraper (not currently functional)

These are the scripts that originally collected the raw data in
`data/raw/fbref/` and `data/match_lists/fbref/`: `league_match_extractor.py`
pulls a season's fixture list from an FBref schedule page,
`match_data_extractor.py` visits each fixture and scrapes the match's box
score, `json_sorterer.py` and `file_checker.py` clean up and validate the
downloaded JSON, and `error_file_deleter.py` removes files that fail
validation. `feature_title_extractor.py` was a one-off helper used earlier
to pull the column names for `src/features_list.json` from FBref's stats
tables.

**FBref changed its page structure after these were written, and the
selectors here no longer pull complete data.** They are included as-is
rather than fixed, because getting them working again is a scraping-
maintenance task, not part of what this project is meant to demonstrate.
They're kept in the repo to show the actual data-collection work behind
`data/processed/training_table.csv`, not as a ready-to-run tool.

Both scrapers use Selenium (so a Chromedriver matching your installed
Chrome is required) plus BeautifulSoup for parsing, and prompt
interactively for which league/season to fetch.
