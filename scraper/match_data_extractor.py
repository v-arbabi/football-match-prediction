from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup
import json
from scraper.file_selector import get_league_season_selection
from src.paths import RAW_MATCH_DIR
import time
import random
import os
from scraper.json_sorterer import main_cleaner

# --- Function to extract both team IDs from the scorebox section ---

def extract_match_metadata(soup, season, match_id, home_id, away_id, match_date, match_time, attendance):
    """
    Extracts metadata for a football match from the 'scorebox' HTML section of FBref.
    Input: a single <div class="scorebox"> element (BeautifulSoup tag, not list)
    Returns a dictionary with team info, score, xG, manager, captain, venue, attendance, etc.
    """
    scorebox = soup.find("div", class_="scorebox")

    def extract_field_from_meta(meta, label):
        """
        Extracts a metadata field like Attendance, Venue, or Officials.
        Handles variations in HTML structure with <strong>, <small>, or direct text.
        """
        for div in meta.find_all("div"):
            # Case 1: <strong><small>Label</small></strong>: <small>Value</small>
            strong = div.find("strong")
            small_output = {}
            if strong:
                small_in_strong = strong.find("small")
                if small_in_strong and label.lower() in small_in_strong.text.lower():
                    value_small = div.find_all("small")
                    if value_small[0].text.strip().lower() == "officials":
                        for span in value_small[1].find_all("span"):
                            span_key = span.text.strip().split(" ")[-1].replace("(", "").replace(")", "")
                            span_value = " ".join(span.text.strip().split(" ")[::-1][1:][::-1])
                            small_output.update({span_key: span_value})
                        return small_output
                    if value_small[0].text.strip().lower() == "venue":
                        return value_small[1].text.strip()

            # Case 2: <strong>Label</strong>: Value
            if strong and label.lower() in strong.text.lower():
                small = div.find("small")
                if small:
                    return small.text.strip()
                # Try next sibling as fallback
                if strong.next_sibling and isinstance(strong.next_sibling, str):
                    return strong.next_sibling.strip().strip(":").strip()

        return None

    meta_data = {}
    try:
        # Get the two team blocks (home and away)
        team_divs = scorebox.find_all("div", recursive=False)[:2]
        home_team = None
        away_team = None
        for div in team_divs:
            team = {}
            # Team name
            name_tag = div.find("strong")
            team["name"] = name_tag.text.strip() if name_tag else None
            # Team ID
            squad_link = div.find("a", href=True)
            if squad_link and "/en/squads/" in squad_link["href"]:
                team["team_id"] = squad_link["href"].split("/")[3]
            # Logo URL
            logo_tag = div.find("img", class_="teamlogo")
            team["logo"] = logo_tag["src"] if logo_tag else None
            # Score
            score_div = div.find("div", class_="score")
            team["score"] = int(score_div.text.strip("*").strip()) if score_div else None
            # xG
            xg_div = div.find("div", class_="score_xg")
            team["xg"] = float(xg_div.text.strip()) if xg_div else None
            # Manager
            manager_div = div.find("div", string=lambda x: x and "Manager" in x)
            if not manager_div:
                manager_div = div.find("div", string=lambda x: x and "Manager" in x)
            if manager_div:
                team["manager"] = manager_div.text.split(":")[-1].strip()
            # Captain
            captain_div = div.find("div", string=lambda x: x and "Captain" in x)
            if not captain_div:
                captain_div = div.find("div", string=lambda x: x and "Captain" in x)
            if captain_div:
                captain_tag = captain_div.find("a")
                team["captain"] = captain_tag.text.strip() if captain_tag else None
            if team["team_id"] == home_id:
                home_team = team
            else:
                away_team = team
        meta_data["home"] = home_team
        meta_data["away"] = away_team

        # Now extract global meta data from scorebox_meta
        scorebox_meta = scorebox.find("div", class_="scorebox_meta")
        if scorebox_meta:
            competition_tag = scorebox_meta.find_all("div")[1].text.strip() if len(scorebox_meta.find_all("div")) > 1 else None
            competition_name = competition_tag.split("(Matchweek")[0].strip().replace(" ", "_")
            week = competition_tag.split(" ")[-1].replace("(", "").replace(")", "").split(" ")[-1]
            meta_data["match_id"] = match_id
            meta_data["competition"] = competition_name
            meta_data["season"] = season
            meta_data["date"] = match_date
            meta_data["time"] = match_time
            meta_data["week"] = week
            meta_data["attendance"] = int(attendance)
            venue_city = extract_field_from_meta(scorebox_meta, "Venue")
            venue = venue_city.split(",")[0].strip()
            city = venue_city.split(",")[1].strip()
            meta_data["venue"] = venue
            meta_data["city"] = city
            meta_data["officials"] = extract_field_from_meta(scorebox_meta, "Officials")

    except Exception as e:
        print(f"[ERROR] Failed to extract metadata: {e}")

    return meta_data

def lineup_extractor(soup, home_id, away_id):
    divs = soup.find_all("div", class_="lineup")
    lineup = {home_id:{"starters": [], "bench":[]}, away_id:{"starters": [], "bench":[]}}

    def lineup_player_extractor(tr, lineup_section):
        td_list = tr.find_all("td")
        shirt_number = td_list[0].text.strip()
        link_tag = tr.find("a")
        if link_tag is not None:
            link = link_tag["href"]
            player_id = link.split("/")[3]
            player_name = link_tag.text.strip()
        events_tag = tr.find_all("div")
        events = []
        for event_tag in events_tag:
            event = event_tag["class"][1]
            events.append(event)
        lineup[team_id][f'{lineup_section}'].append({
            "player_id": player_id,
            "player_name": player_name,
            "shirt_number": int(shirt_number),
            "team_id": team_id,
            "events": events})

    for div in divs:
        team = None
        if div["id"] == "a":
            team_id = home_id
            team = "home"
        else:
            team_id = away_id
            team = "away"
        tbody = div.find("tbody")

        tr_list = tbody.find_all("tr")
        bench_index = None
        for tr in tr_list:
            if tr.find("th"):
                if tr.find("th").text.strip() == "Bench":
                    bench_index = tr_list.index(tr)
        starters_tr = tr_list[1:bench_index]
        bench_tr = tr_list[bench_index+1:]
        player = player_id = player_name = team_name = formation = None
        tr_info = tr_list[0]
        tr_info_len = len(list(tr_info.text.strip().split(" ")))
        team_name = "_".join(tr_list[0].text.strip().split(" ")[0:tr_info_len-1])
        formation = tr_list[0].text.strip().split(" ")[-1].replace("(", "").replace(")", "")

        for tr in starters_tr:
            lineup_section = "starters"
            lineup_player_extractor(tr, lineup_section)
        for tr in bench_tr:
            lineup_section = "bench"
            lineup_player_extractor(tr, lineup_section)

        lineup[team_id].update({"team_id": team_id, "team_name": team_name,"side":team, "formation": formation})
    return lineup



# --- Function to extract detailed player stats for a specific team ---
def extract_team_tables(soup, team_id):
    """
    Extracts player stats for a given team from all relevant stat tables.
    Returns a dictionary: {team_id: {players: {...}}}
    """
    table_suffixes = ["summary", "passing", "passing_types", "defense", "possession", "misc"]
    stat_table_ids = [f"stats_{team_id}_{suffix}" for suffix in table_suffixes]

    team_data = {
        team_id: {
            "stats": {},
            "players": {}
        }
    }

    for table_id in stat_table_ids:
        table = soup.find("table", id=table_id)
        if table is None:
            continue

        tbody = table.find("tbody")
        if tbody is None:
            continue

        for tr in tbody.find_all("tr"):
            player_id = None
            player_row = {"information": {}, "stats": {}}
            cols = tr.find_all(["th", "td"])

            for cell in cols:
                stat = cell.get("data-stat")

                if cell.has_attr("data-append-csv"):
                    player_id = cell["data-append-csv"]
                    name_tag = cell.find("a")
                    if name_tag:
                        player_row["information"]["player_name"] = name_tag.text.strip()
                    player_row["information"]["player_id"] = player_id
                    player_row["information"]["team_id"] = team_id

                elif stat == "nationality":
                    nationality_tag = cell.find("a")
                    if nationality_tag:
                        nat = nationality_tag.text.strip()
                        player_row["information"]["nationality"] = nat[-3:]
                elif stat == "shirtnumber":
                    player_row["information"]["shirtnumber"] = cell.text.strip()
                elif stat == "position":
                    player_row["information"]["position"] = cell.text.strip()
                elif stat == "age":
                    player_row["information"]["age"] = cell.text.strip()
                elif stat:
                    string = cell.text.strip()
                    try:
                        if "." in string:
                            number = float(string)
                        elif string == "":
                            number = 0
                        else:
                            number = int(string)
                    except ValueError:
                        number = 0
                    player_row["stats"][stat] = number


            # Store data only if player_id is found
            if player_id:
                if player_id not in team_data[team_id]["players"]:
                    team_data[team_id]["players"][player_id] = {
                        "information": player_row["information"],
                        "stats": player_row["stats"]
                    }
                else:
                    team_data[team_id]["players"][player_id]["stats"].update(player_row["stats"])
        tfoot = table.find("tfoot")
        for tr in tfoot.find_all("tr"):
            cols = tr.find_all(["th", "td"])
            for cell in cols:
                stat = cell.get("data-stat")
                if stat not in ["player", "shirtnumber", "nationality", "position", "age"]:
                    string = cell.text.strip()
                    try:
                        if "." in string:
                            number = float(string)
                        elif string == "":
                            number = 0
                        else:
                            number = int(string)
                    except ValueError:
                        number = 0
                    team_data[team_id]["stats"][stat] = number
    return team_data

def extract_goal_keepers(soup, home_id, away_id):
    goal_keepers = {home_id: {}, away_id: {}}
    for team_id in [home_id, away_id]:
        table = soup.find("table", id=f'keeper_stats_{team_id}')
        tbody = table.find("tbody")
        for tr in tbody.find_all("tr"):
            goalkeeper_id = None
            goalkeeper_row = {"information": {}, "stats": {}}
            cols = tr.find_all(["th", "td"])
            for cell in cols:
                stat = cell.get("data-stat")
                if cell.has_attr("data-append-csv"):
                    goalkeeper_id = cell["data-append-csv"]
                    name_tag = cell.find("a")
                    if name_tag:
                        goalkeeper_row["information"]["player_name"] = name_tag.text.strip()
                    goalkeeper_row["information"]["player_id"] = goalkeeper_id
                    goalkeeper_row["information"]["team_id"] = team_id
                elif stat == "nationality":
                    nationality_tag = cell.find("a")
                    if nationality_tag:
                        nat = nationality_tag.text.strip()
                        goalkeeper_row["information"]["nationality"] = nat[-3:]
                elif stat == "age":
                    goalkeeper_row["information"]["age"] = cell.text.strip()
                elif stat:
                    string = cell.text.strip()
                    try:
                        if "." in string:
                            number = float(string)
                        elif string == "":
                            number = 0
                        else:
                            number = int(string)
                    except ValueError:
                        number = 0
                    goalkeeper_row["stats"][stat] = number
            if goalkeeper_id:
                if goalkeeper_id not in goal_keepers[team_id]:
                    goal_keepers[team_id][goalkeeper_id] = {
                        "information": goalkeeper_row["information"],
                        "stats": goalkeeper_row["stats"]
                    }
    return goal_keepers


# --- Function to extract all shots from both teams (combined shots table) ---
def extract_shots_table(soup, team_id):
    """
    Extracts all shot events from the 'shots_all' table.
    Includes player info, shot type, result, location, etc.
    """
    shots_data = []
    table = soup.find("table", id=f'shots_{team_id}')
    if not table:
        return shots_data

    tbody = table.find("tbody")
    if not tbody:
        return shots_data

    for tr in tbody.find_all("tr"):
        shot_row = {}
        cols = tr.find_all(["th", "td"])

        # Extract player ID (if available)
        for cell in cols:
            if cell.has_attr("data-append-csv"):
                shot_row["player_id"] = cell["data-append-csv"]

        # Extract other stat values
        for cell in cols:
            stat = cell.get("data-stat")
            if stat == "nationality":
                nationality_tag = cell.find("a")
                if nationality_tag:
                    nat = nationality_tag.text.strip()
                    shot_row["nationality"] = nat[-3:]
            elif stat:
                shot_row[stat] = cell.text.strip()

        shots_data.append(shot_row)

    return shots_data

# --- Function to extract event timeline (goals, substitutions, cards, etc.) ---
def extract_summary_data(soup):
    """
    Extracts all major in-match events from the timeline area of the page.
    Covers goals, yellow/red cards, substitutions and their timings.
    """
    events = []
    event_wrap = soup.find("div", id="events_wrap")
    if not event_wrap:
        return events

    try:
        event_a = event_wrap.find_all("div", class_=lambda x: x and "event" in x.split() and "a" in x.split())
        event_b = event_wrap.find_all("div", class_=lambda x: x and "event" in x.split() and "b" in x.split())
        event_ab = event_a + event_b

        for a in event_ab:
            event = {}

            # Extract event time (e.g., "45+1")
            event_time_div = a.find("div")
            if event_time_div:
                event["event_time"] = event_time_div.text.strip().split("’")[0]

            # Extract event type and related players
            hidden_text = a.find("div", style="display: none;")
            if hidden_text:
                event_type = hidden_text.text.strip().split("xa0")[0]
                event["event_type"] = event_type

                if event_type == "Substitute":
                    players = a.find_all("a", href=True)
                    if len(players) >= 2:
                        event["player_in"] = players[0].text.strip()
                        event["player_in_id"] = players[0].get("href", "").split("/")[2]
                        event["player_out"] = players[1].text.strip()
                        event["player_out_id"] = players[1].get("href", "").split("/")[2]
                else:
                    player_link = a.find("a", href=True)
                    if player_link:
                        event["event_player"] = player_link.text.strip()
                        event["event_player_id"] = player_link.get("href", "").split("/")[3]

                    team_logo = a.find("img", class_="teamlogo")
                    if team_logo:
                        src = team_logo.get("src", "")
                        event["event_team"] = src.split("/fb/")[1].split(".")[0]

            events.append(event)
    except Exception as e:
        print(f"Error in extract_summary_data: {e}")
        return events

    return events

# --- Master function to extract all match data ---
def extract_match_data(driver ,match_link, season, match_id, home, home_id, away, away_id, date, time, attendance):
    driver.get(match_link)
    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "shots_all")))
    soup = BeautifulSoup(driver.page_source, "html.parser")

    meta_data = extract_match_metadata(soup, season, match_id, home_id, away_id, date, time, attendance)
    # Get both team IDs
    scorebox = soup.find_all("div", class_="scorebox")
    goalkeepers = extract_goal_keepers(soup, home_id, away_id)
    # Team stats for both teams
    all_team_stats = {}
    for tid in [home_id, away_id]:
        all_team_stats.update(extract_team_tables(soup, tid))
    shots_data = {}
    for tid in [home_id, away_id]:
        shot_data = extract_shots_table(soup, tid)
        shots_data.update({tid: shot_data})
    time_line = extract_summary_data(soup)
    for team_idx in goalkeepers.keys():
        team_goalkeeper = {}
        for goalkeeper_id in goalkeepers[team_idx].keys():
            team_goalkeeper.update({goalkeeper_id:goalkeepers[team_idx][goalkeeper_id]})
        all_team_stats[team_idx].update({"goalkeeper":team_goalkeeper})
    lineup = lineup_extractor(soup, home_id, away_id)
    return {
        "meta_data": meta_data,
        "lineup": lineup,
        "team_stats": all_team_stats,
        "shots": shots_data,
        "timeline": time_line
    }
if __name__ == "__main__":
    source = "fbref"
    league_name, season_name, match_list = get_league_season_selection(source)
    season_dir = os.path.join(RAW_MATCH_DIR, source, league_name, season_name.lower())
    os.makedirs(season_dir, exist_ok=True)

    existing_files = os.listdir(season_dir)
    existing_ids = {f.split("_")[0] for f in existing_files if f.endswith(".json")}
    print(f"📂 Existing match IDs: {existing_ids}")

    options = Options()
    driver = webdriver.Chrome(options=options)
    for match_id in match_list.keys():
        if match_id in existing_ids:
            print(f"🔁 Skipping existing match ID: {match_id}")
            continue
        match_link = match_list[match_id]["match_link"]
        match_date = match_list[match_id]["match_date"]
        match_time = match_list[match_id]["match_time"]
        attendance = match_list[match_id]["attendance"]
        home = match_list[match_id]["home"]
        home_id = match_list[match_id]["home_id"]
        away = match_list[match_id]["away"]
        away_id = match_list[match_id]["away_id"]
        match_data = extract_match_data(driver, match_link, season_name, match_id, home, home_id, away, away_id, match_date, match_time, attendance)
        cleaned_match_data = main_cleaner(match_data)
        league_season_path = os.path.join(RAW_MATCH_DIR, source,league_name, season_name)
        os.makedirs(league_season_path, exist_ok=True)
        file_name = "_".join([match_id, source, league_name, season_name, home.replace(" ", "_"), away.replace(" ", "_")]) + ".json"
        print(f'\n {file_name}: saved. \n')
        file_path = os.path.join(league_season_path, file_name)
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_match_data, f, indent=2)
        time.sleep(random.uniform(2, 5))
