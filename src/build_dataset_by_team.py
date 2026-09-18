import json
import os
from src import build_dataset_by_matches


def teams_matches_dict_creator(matches_list):
    # Build {team_id: []} for all teams appearing in the season
    teams = set()
    for match in matches_list:
        # print(matches_list)
        teams.add(match["home"]["team_id"])
        teams.add(match["away"]["team_id"])
    return {team_id: [] for team_id in teams}


def meta_data_extractor(match_data):
    # Extract minimal, stable metadata used downstream
    meta = match_data["meta"]
    return {
        "match_id": meta["match_id"],
        "date": meta["date"],              # 'YYYYMMDD'
        "time_GMT": meta["time_GMT"],
        "league": meta["tournament"].lower(),
        "season": meta["season"],
        "week_round": meta["week_round"],
    }


def target_extractor(match_data, team):
    # Build targets: team_goals, opponent_goals, BTTS, Over2.5
    home_goals = match_data["home"]["team_stat"]["goals"]
    away_goals = match_data["away"]["team_stat"]["goals"]

    btts = 1 if (home_goals > 0 and away_goals > 0) else 0
    over25 = 1 if (home_goals + away_goals > 2) else 0

    if team == "home":
        return {
            "team_goals": home_goals,
            "opponent_goals": away_goals,
            "btts": btts,
            "over25": over25,
        }
    else:
        return {
            "team_goals": away_goals,
            "opponent_goals": home_goals,
            "btts": btts,
            "over25": over25,
        }


def _safe_stat(match_data, side, feature):
    # Safely read a team_stat feature; default to 0 if missing
    return match_data[side]["team_stat"].get(feature, 0)


def team_match_extractor(team, match_data, feature_list):
    # Build per-team match record with own stats + opponent (…_against)
    team_match = {"stat": {}}
    team_match["team_id"] = match_data[team]["team_id"]
    team_match["team_name"] = match_data[team]["team_name"]

    if team == "home":
        team_match["is_home"] = 1
        opp = "away"
    else:
        team_match["is_home"] = 0
        opp = "home"

    team_match["opponent_id"] = match_data[opp]["team_id"]
    team_match["opponent_name"] = match_data[opp]["team_name"]

    for feature in feature_list:
        team_match["stat"][feature] = _safe_stat(match_data, team, feature)
        team_match["stat"][f"{feature}_against"] = _safe_stat(match_data, opp, feature)

    return team_match, team_match["team_id"]


# --------- NEW: time-index helpers (add these) ---------
def _date_to_int(date_str):
    # Convert 'YYYYMMDD' to integer for fast comparison
    return int(date_str)


def sort_team_matches_inplace(teams_matches):
    """
    Sort matches for each team in-place by (date, match_id).
    This ensures stable chronological order before rolling.
    """
    for team_id, matches in teams_matches.items():
        matches.sort(key=lambda m: (_date_to_int(m["date"]), m["match_id"]))
# -------------------------------------------------------


def main():
    # Load feature list (array of strings)
    features_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "features_list.json")
    with open(features_path, "r", encoding="utf-8") as f:
        feature_list = json.load(f)

    # Build season (list of raw matches with meta/home/away)
    league_matches = build_dataset_by_matches.main()
    matches_list = league_matches


    # Init {team_id: [records]}
    teams_matches_dict = teams_matches_dict_creator(matches_list)

    # Expand each match into two team-centric records
    for match in matches_list:
        for team in ["home", "away"]:
            team_match, team_id = team_match_extractor(team, match, feature_list)
            team_match.update(meta_data_extractor(match))
            team_match["targets"] = target_extractor(match, team)

            # keep own stats first, then opponent stats (…_against)
            team_stat = {}
            opp_stat = {}
            for key, value in team_match["stat"].items():
                if "against" in key:
                    opp_stat[key] = value
                else:
                    team_stat[key] = value

            sorted_team_match = {
                "match_id": team_match["match_id"],
                "date": team_match["date"],
                "time_GMT": team_match["time_GMT"],
                "league": team_match["league"],
                "season": team_match["season"],
                "week_round": team_match["week_round"],
                "team_id": team_match["team_id"],
                "team_name": team_match["team_name"],
                "is_home": team_match["is_home"],
                "opponent_id": team_match["opponent_id"],
                "opponent_name": team_match["opponent_name"],
                "targets": team_match["targets"],
                "stat": {}
            }
            sorted_team_match["stat"].update(team_stat)
            sorted_team_match["stat"].update(opp_stat)

            teams_matches_dict[team_id].append(sorted_team_match)

    # NEW: ensure chronological order per team before any rolling
    sort_team_matches_inplace(teams_matches_dict)

    return teams_matches_dict


if __name__ == "__main__":
    teams_matches = main()
    print(json.dumps(teams_matches, indent=2, ensure_ascii=False))