#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# Reads raw per-match FBref JSON for a league/season and normalizes it into
# a flat meta/home/away shape. Team stats (goals, xG, shots, etc.) only
# live under team_stat so nothing gets duplicated between meta and the
# per-side blocks.

import os
import json
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from src.paths import FBREF_RAW_MATCH


def to_iso_utc(date_str: str, time_gmt: Optional[str]) -> str:
    """'YYYYMMDD' + 'HH:MM:SS' (GMT) -> 'YYYY-MM-DDTHH:MM:SSZ' (UTC)."""
    if not time_gmt or len(time_gmt) < 5:
        time_gmt = "12:00:00"  # a handful of older matches are missing kickoff time
    dt = datetime.strptime(f"{date_str} {time_gmt}", "%Y%m%d %H:%M:%S").replace(tzinfo=timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def list_json_files(folder: Path) -> List[Path]:
    """Sorted list of .json files in a folder, so file order is deterministic."""
    if not folder.exists() or not folder.is_dir():
        raise FileNotFoundError(f"Input folder not found: {folder}")
    return sorted(p for p in folder.iterdir() if p.is_file() and p.suffix.lower() == ".json")


def read_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def build_match(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Normalize one raw match (meta_data/home/away) into the shape the rest
    of the pipeline expects. Team-level stats stay under team_stat only -
    goals/xG aren't duplicated into meta.
    """
    meta = record.get("meta_data", {})
    home = record.get("home", {})
    away = record.get("away", {})

    # A few fields are required; if any is missing this match gets skipped
    # rather than crashing the whole load.
    try:
        match_id = meta["match_id"]
        date_raw = meta["date"]
        time_raw = meta.get("time_GMT", "12:00:00")
        home_name = home["team_name"]
        home_id = home["team_id"]
        away_name = away["team_name"]
        away_id = away["team_id"]
    except KeyError:
        return None

    kickoff_dt = to_iso_utc(str(date_raw), str(time_raw))  # used to sort matches chronologically later

    out = {
        "meta": {
            "match_id": match_id,
            "kickoff_dt": kickoff_dt,
            "date": meta.get("date"),
            "time_GMT": meta.get("time_GMT"),
            "tournament": meta.get("tournament"),
            "season": meta.get("season"),
            "week_round": meta.get("week_round"),
            "attendance": meta.get("attendance"),
            "venue": meta.get("venue"),
            "city": meta.get("city"),
            "home_id": meta.get("home_id"),
            "away_id": meta.get("away_id"),
            "referee": (meta.get("referee") or "").replace(" ", " "),
        },
        "home": {
            "team_name": home_name,
            "team_id": home_id,
            "team_stat": home.get("team_stat", {}),
        },
        "away": {
            "team_name": away_name,
            "team_id": away_id,
            "team_stat": away.get("team_stat", {}),
        },
    }
    return out


def build_match_dataset(selected_league, selected_season) -> List[Dict[str, Any]]:
    """Read every match JSON in one league/season folder and return them sorted by kickoff."""
    league_season_path = os.path.join(FBREF_RAW_MATCH, selected_league, selected_season)
    folder = Path(league_season_path)
    files = list_json_files(folder)
    matches: List[Dict[str, Any]] = []
    skipped: List[str] = []

    for p in files:
        try:
            raw = read_json(p)
            m = build_match(raw)
            if m is None:
                skipped.append(f"{p.name} (missing essentials)")
                continue
            matches.append(m)
        except Exception as e:
            skipped.append(f"{p.name} (error: {e})")

    # Rolling-window features downstream assume matches arrive in date order.
    matches.sort(key=lambda x: x["meta"].get("kickoff_dt", ""))

    print(f"[info] matches: {len(matches)} | skipped: {len(skipped)}")
    for msg in skipped[:10]:
        print(f"[skip] {msg}")
    if len(skipped) > 10:
        print(f"[skip] ... {len(skipped) - 10} more")

    return matches


def discover_league_seasons():
    """
    Look at what's actually on disk under data/raw/fbref/ instead of a
    hardcoded league/season list, so this works whether one league is
    populated or eight, without touching this file. Most league folders
    in this repo are empty placeholders (only two real sample match files
    ship here), so a (league, season) pair only counts if its folder
    actually has at least one .json file in it.
    """
    pairs = []
    if not os.path.isdir(FBREF_RAW_MATCH):
        return pairs
    for league in sorted(os.listdir(FBREF_RAW_MATCH)):
        league_dir = os.path.join(FBREF_RAW_MATCH, league)
        if not os.path.isdir(league_dir):
            continue
        for season in sorted(os.listdir(league_dir)):
            season_dir = os.path.join(league_dir, season)
            if not os.path.isdir(season_dir):
                continue
            has_json = any(f.lower().endswith(".json") for f in os.listdir(season_dir))
            if has_json:
                pairs.append((league, season))
    return pairs


def main():
    pairs = discover_league_seasons()
    if not pairs:
        print(f"[build_dataset_by_matches] no raw match JSON found under {FBREF_RAW_MATCH}")

    dataset_list = list()
    for league, season in pairs:
        print(f"[build_dataset_by_matches] loading {league}/{season}")
        matches = build_match_dataset(league, season)
        dataset_list.extend(matches)
    return dataset_list


if __name__ == "__main__":
    league_matches = main()
    # print(json.dumps(league_matches, ensure_ascii=False, indent=2))
