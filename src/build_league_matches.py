import json
from src import build_dataset_by_team


def main():
    team_matches_dict = build_dataset_by_team.main()
    league_matches = dict()
    date_index_by_team = dict()
    for team, matches in team_matches_dict.items():
        for match in matches:
            match_id = match["match_id"]
            league_name = match["league"].lower()
            season = match["season"]
            date = match["date"]
            team_id = match["team_id"]
            key = f'{league_name}_{season}_{date}_{match_id}_{team_id}'
            league_matches.update({key: match})
            if not date_index_by_team.get(team_id):
                date_index_by_team[team_id] = list()
                date_index_by_team[team_id].append(date)
            else:
                date_index_by_team[team_id].append(date)
                date_index_by_team[team_id].sort()

    return league_matches, date_index_by_team


if __name__ == "__main__":
    league_matches_dict, date_index_by_team_dict = main()
    # print(json.dumps(date_index_by_team_dict, indent=2))
    print(json.dumps(league_matches_dict, indent=2))