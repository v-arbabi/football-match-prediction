import json

def lineup_cleaner(data, cleaned_json):
    for team_id in data["lineup"].keys():
        players = []
        side = None
        if team_id == data["meta_data"]["home"]["team_id"]:
            side = "home"
        else:
            side = "away"
        lineup_sections = ["starters", "bench"]
        for lineup_section in lineup_sections:
            for player in data["lineup"][team_id][lineup_section]:
                is_starter = False
                if lineup_section == "starters":
                    is_starter = True
                is_substituted = False
                if "substitute_in" in player["events"]:
                    is_substituted = True
                players.append({"player_id": player["player_id"], "player_name": player["player_name"],
                                "team_id": player["team_id"], "is_starter": is_starter,
                                "is_substituted": is_substituted})
        cleaned_json[side]["lineup"].extend(players)


def shot_data_cleaner(data, cleaned_json):
    team_ids = list(data["shots"].keys())
    for team_id in team_ids:
        side = None
        if team_id == data["meta_data"]["home"]["team_id"]:
            side = "home"
        else:
            side = "away"
        for player in data["shots"][team_id]:
            if player.get("player_id"):
                cleaned_json[side]["shot_stat"].append(player)

def team_stat_data_cleaner(data, cleaned_json, ):
    team_ids = list(data["team_stats"].keys())
    for team_id in team_ids:
        side = None
        if team_id == data["meta_data"]["home"]["team_id"]:
            side = "home"
        else:
            side = "away"
        cleaned_json[side]["team_stat"].update(data["team_stats"][team_id]["stats"])
        cleaned_json[side]["players_stat"].update(data["team_stats"][team_id]["players"])
        cleaned_json[side]["goalkeeper_stat"].update(data["team_stats"][team_id]["goalkeeper"])


def main_cleaner(data):
    cleaned_json = {
        "meta_data": {
            "match_id": data["meta_data"]["match_id"],
            "date": data["meta_data"]["date"],
            "time_GMT": data["meta_data"]["time"],
            "tournament": data["meta_data"]["competition"],
            "season": data["meta_data"]["season"],
            "week_round": data["meta_data"]["week"],
            "home": data["meta_data"]["home"]["name"],
            "home_id": data["meta_data"]["home"]["team_id"],
            "home_score": data["meta_data"]["home"]["score"],
            "home_xg": data["meta_data"]["home"]["xg"],
            "away": data["meta_data"]["away"]["name"],
            "away_id": data["meta_data"]["away"]["team_id"],
            "away_score": data["meta_data"]["away"]["score"],
            "away_xg": data["meta_data"]["away"]["xg"],
            "attendance": data["meta_data"]["attendance"],
            "venue": data["meta_data"]["venue"],
            "city": data["meta_data"]["city"],
            "referee": data["meta_data"]["officials"]["Referee"],
            "referee_assistant1": data["meta_data"]["officials"]["AR1"],
            "referee_assistant2": data["meta_data"]["officials"]["AR2"],
            "referee_4th": data["meta_data"]["officials"]["4th"],

        },
        "home": {
            "team_name": data["meta_data"]["home"]["name"],
            "team_id": data["meta_data"]["home"]["team_id"],
            "score": data["meta_data"]["home"]["score"],
            "xg": data["meta_data"]["home"]["xg"],
            "lineup": [],
            "team_stat": {},
            "players_stat": {},
            "goalkeeper_stat": {},
            "shot_stat": []
        },
        "away": {
            "team_name": data["meta_data"]["away"]["name"],
            "team_id": data["meta_data"]["away"]["team_id"],
            "score": data["meta_data"]["away"]["score"],
            "xg": data["meta_data"]["away"]["xg"],
            "lineup": [],
            "team_stat": {},
            "players_stat": {},
            "goalkeeper_stat":{},
            "shot_stat": []
        }
    }
    lineup_cleaner(data, cleaned_json)
    shot_data_cleaner(data, cleaned_json)
    team_stat_data_cleaner(data,cleaned_json)
    return cleaned_json
