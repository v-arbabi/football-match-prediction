import os
import json

from src.paths import MATCH_LIST_DIR


def list_available_leagues(source):
    """
    Lists all league directories in the match_lists folder.
    """
    source_path = os.path.join(MATCH_LIST_DIR, source)
    if not os.path.exists(source_path):
        raise FileNotFoundError(f"❌ Directory not found: {source_path}")

    leagues = [d for d in os.listdir(source_path) if os.path.isdir(os.path.join(source_path, d))]
    if not leagues:
        raise FileNotFoundError("❌ No leagues found inside match_lists folder.")

    return leagues


def get_league_season_selection(source):
    """
    Interactively selects a league and a season JSON file.
    """
    leagues = list_available_leagues(source=source)
    print("Available leagues:")
    for idx, league in enumerate(leagues, 1):
        print(f"{idx}. {league}")

    league_idx = int(input("Choose league (number): ")) - 1
    if not (0 <= league_idx < len(leagues)):
        raise ValueError("❌ Invalid league selection.")

    selected_league = leagues[league_idx]
    league_path = os.path.join(MATCH_LIST_DIR, source, selected_league.replace(" ","_"))

    # List season JSON files
    if not os.path.exists(league_path):
        raise FileNotFoundError(f"❌ League folder not found: {league_path}")

    seasons = [f for f in os.listdir(league_path) if f.endswith(".json")]
    if not seasons:
        raise FileNotFoundError(f"❌ No season JSON files found in {league_path}.")

    print("Available seasons:")
    for idx, season in enumerate(seasons, 1):
        print(f"{idx}. {season}")

    season_idx = int(input("Choose season (number): ")) - 1
    if not (0 <= season_idx < len(seasons)):
        raise ValueError("❌ Invalid season selection.")

    selected_season = seasons[season_idx]
    season_path = os.path.join(league_path, selected_season)

    # Load the JSON match list
    with open(season_path, "r", encoding="utf-8") as f:
        match_list = json.load(f)

    league_name = selected_league  # e.g., "premier_league"
    season_name = selected_season.replace(".json", "")  # e.g., "Premier_League_2014_2015"
    season_name = season_name.split("_")[-2] + "_" + season_name.split("_")[-1]

    return league_name, season_name, match_list


leagues = {
    "premier league": "9",
    "la liga": "12",
    "bundesliga": "20",
    "ligue 1": "13",
    "serie a": "11"
}
seasons = ["2017-2018", "2018-2019", "2019-2020",
           "2020-2021", "2021-2022", "2022-2023",
           "2023-2024", "2024-2025", "2025-2026"]

def league_season_selector():
    league_names = list(leagues.keys())
    print("Available leagues:")
    for idx, league in enumerate(league_names, 1):
        print(f"{idx}. {league}")

    league_idx = int(input("Choose league (number): ")) - 1
    if not (0 <= league_idx < len(league_names)):
        raise ValueError("❌ Invalid league selection.")
    selected_league = league_names[league_idx]
    selected_league_code = leagues[selected_league]
    print("Available seasons:")
    for idx, season in enumerate(seasons, 1):
        print(f"{idx}. {season}")

    season_idx = int(input("Choose season (number): ")) - 1
    if not (0 <= season_idx < len(seasons)):
        raise ValueError("❌ Invalid league selection.")
    selected_season = seasons[season_idx].replace("-", "_")
    return selected_league.replace(" ", "_"), selected_season, selected_league_code

def json_loader(json_path):
    with open(json_path, "r",encoding="utf-8") as f:
        data = json.load(f)
    return data