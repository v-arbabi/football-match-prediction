import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
from src.paths import MATCH_LIST_DIR

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

def league_season_link_maker():
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
    selected_season = seasons[season_idx]
    url = f'https://fbref.com/en/comps/{selected_league_code}/{selected_season}/schedule/'
    return url, selected_league, selected_season, selected_league_code
def match_extractor(driver, selected_league_code, selected_season):
    soup = BeautifulSoup(driver.page_source, "html.parser")
    table_id = f'sched_{selected_season}_{selected_league_code}_1'
    table = soup.find("table", id=table_id)
    tbody = table.find("tbody")
    fbref_matches = {}
    for tr in tbody.find_all("tr"):
        match_date = match_time = match_id_bref = match_link = home = away = None
        attendance = 0
        for td in tr.find_all(["th", "td"]):
            stat = td.get("data-stat")
            if stat == "gameweek":
                game_week = td.text.strip()
            if stat == "date":
                match_date = td.get("csk")
            elif stat == "start_time":
                match_time = td.get("csk")
            elif stat == "attendance":
                if td.get("csk"):
                    attendance = td.get("csk")
            elif stat == "score" and td.find('a'):
                href = td.find('a')['href']
                match_id_bref = href.split("/")[3]
                match_link = "https://fbref.com" + href
            elif stat == "home_team" and td.find('a'):
                home = td.find('a').text.strip()
                home_id = td.find('a')['href'].split("/squads/")[1].split("/")[0]
            elif stat == "away_team" and td.find('a'):
                away = td.find('a').text.strip()
                away_id = td.find('a')['href'].split("/squads/")[1].split("/")[0]
        if match_id_bref:
            fbref_matches[match_id_bref] = {
                "match_id": match_id_bref,
                "match_link": match_link,
                "match_date": match_date,
                "match_time": match_time,
                "game_week": game_week,
                "attendance": attendance,
                "home": home,
                "home_id": home_id,
                "away": away,
                "away_id": away_id
            }
    return fbref_matches
def league_matches_extractor():
    url, league, season, selected_league_code = league_season_link_maker()
    driver = webdriver.Chrome()
    driver.get(url)
    WebDriverWait(driver, 15)
    matches_list = match_extractor(driver, selected_league_code, season)
    file_name = "fbref_" + league.replace(" ", "_") + "_" + season.replace("-", "_") + ".json"
    # print(json.dumps(matches_list, indent=2))
    return matches_list, file_name, league, season

if __name__ == "__main__":
    match_list_data , file_name, league, season = league_matches_extractor()
    league_path = os.path.join(MATCH_LIST_DIR, "fbref", league.replace(" ", "_"))
    os.makedirs(league_path, exist_ok=True)
    file_path = os.path.join(league_path, file_name)
    print(json.dumps(match_list_data, indent=2))
    print(f'\n {len(match_list_data)} matches have been saved.')
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(match_list_data, f, indent=2)