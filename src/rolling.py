# src/rolling.py
# --------------------------------------------------------------
# Build 5-game rolling COMBO features WITHOUT venue split.
# COMBO(s) for a match:
#   - home:  median(last5_home_team[s]) + median(last5_away_team[s_against])
#   - away:  median(last5_away_team[s]) + median(last5_home_team[s_against])
# STRICT policy: if any required window/value is missing -> skip the match row.
# No variance, no Poisson; just medians for stability.
# --------------------------------------------------------------

import json
from collections import defaultdict
from datetime import datetime, timedelta
from statistics import median

# Project loader: returns per-team per-match records
from src import build_league_matches

WINDOW = 5          # number of prior matches (any venue) to use
MAX_AGE_DAYS = 180  # oldest match in the 5-game window must be within this many days of current

# ---------------- helpers ----------------

def parse_date(s: str) -> datetime:
    """Parse YYYYMMDD (may arrive as int/str) to datetime."""
    return datetime.strptime(str(s), "%Y%m%d")

def within_cutoff(cur: str, past: str) -> bool:
    """Ensure the oldest game in the 5-game window is not too old."""
    return (parse_date(cur) - parse_date(past)) <= timedelta(days=MAX_AGE_DAYS)

def discover_pairs_from_stat(sample_stat: dict):
    """
    Auto-discover (s, s_against) pairs from one example stat dict.
    Keeps keys where both 's' and 's_against' exist.
    """
    pairs = []
    if not isinstance(sample_stat, dict):
        return pairs
    for k in sample_stat.keys():
        if k.endswith("_against"):
            continue
        ak = k + "_against"
        if ak in sample_stat:
            pairs.append((k, ak))
    return pairs

# ---------------- core ----------------

def build_window():
    """
    Steps:
      1) Load raw per-team match records (no venue split).
      2) For each team, make a single chronological list of dates (all matches).
      3) Build strict rolling medians over last 5 matches for each (stat, stat_against).
      4) For each match (home vs away), emit COMBO features if both sides have windows.
    Returns:
      dict[row_key] -> row with meta + targets + w5_combo_* features
    """
    # 1) Load data structures from pipeline
    league_matches, date_index_by_team, *_ = build_league_matches.main()

    # Indexes to make windowing and joining easy
    by_team_date = defaultdict(dict)   # team_id -> {date: (key, record)}
    dates_by_team = defaultdict(list)  # team_id -> [date1, date2, ...] (ALL matches, any venue)
    match_sides = defaultdict(dict)    # (league, season, date, match_id) -> {'home': key, 'away': key}
    sample_stat = None                 # one example 'stat' dict to learn pairs

    # Walk all records once
    for key, rec in league_matches.items():
        tid = rec["team_id"]
        d = rec["date"]
        by_team_date[tid][d] = (key, rec)
        dates_by_team[tid].append(d)

        mkey = (rec["league"], rec["season"], rec["date"], rec["match_id"])
        if rec.get("is_home") in (1, True):
            match_sides[mkey]["home"] = key
        else:
            match_sides[mkey]["away"] = key

        if sample_stat is None and isinstance(rec.get("stat"), dict):
            sample_stat = rec["stat"]

    # Chronological order per team (all matches)
    for tid in dates_by_team:
        dates_by_team[tid].sort()

    # Discover (s, s_against) pairs
    pairs = discover_pairs_from_stat(sample_stat)
    if not pairs:
        raise ValueError("No <stat, stat_against> pairs discovered in 'stat' dicts.")

    # Per (team, current_date) we will store medians from its last 5 matches (ALL matches, any venue)
    team_w5_for   = {}  # key -> { s: median(...) }
    team_w5_again = {}  # key -> { s_against: median(...) }

    def roll_team_all_matches(team_id, dates_sorted):
        """
        Build strict 5-game rolling medians for one team, across ALL matches (no venue split).
        """
        n = len(dates_sorted)
        if n < WINDOW + 1:
            return
        for idx in range(WINDOW, n):
            cur_date   = dates_sorted[idx]
            first_date = dates_sorted[idx - WINDOW]
            if not within_cutoff(cur_date, first_date):
                continue

            vals_for, vals_again = defaultdict(list), defaultdict(list)
            complete = True

            # Collect raw values from the previous WINDOW matches
            for j in range(idx - WINDOW, idx):
                _, past_rec = by_team_date[team_id][dates_sorted[j]]
                stat = past_rec.get("stat", {}) or {}
                for s, sa in pairs:
                    if s not in stat or sa not in stat:
                        complete = False
                        break
                    try:
                        vals_for[s].append(float(stat[s]))
                        vals_again[sa].append(float(stat[sa]))
                    except Exception:
                        complete = False
                        break
                if not complete:
                    break

            if not complete:
                continue

            # Store medians for current match key of this team
            cur_key, _ = by_team_date[team_id][cur_date]
            team_w5_for[cur_key]   = {s: median(vals_for[s])     for s, sa in pairs}
            team_w5_again[cur_key] = {sa: median(vals_again[sa]) for s, sa in pairs}

    # Build rolling windows for all teams
    for tid, dlist in dates_by_team.items():
        roll_team_all_matches(tid, dlist)

    # Emit one row per match, combining both sides’ medians into COMBO features
    rows = {}
    kept, skipped = 0, 0

    for (league, season, date, match_id), sides in match_sides.items():
        hk = sides.get("home")
        ak = sides.get("away")
        if not hk or not ak:
            skipped += 1
            continue

        # Both sides must have last-5 medians at *this* current date
        if hk not in team_w5_for or hk not in team_w5_again:
            skipped += 1
            continue
        if ak not in team_w5_for or ak not in team_w5_again:
            skipped += 1
            continue

        home_rec = league_matches[hk]
        away_rec = league_matches[ak]

        hf = team_w5_for[hk]      # medians of home team 'for'
        ha = team_w5_again[hk]    # medians of home team 'against'
        af = team_w5_for[ak]      # medians of away team 'for'
        aa = team_w5_again[ak]    # medians of away team 'against'

        # Prepare meta + targets from the HOME perspective
        row_key = f"{league}_{season}_{date}_{match_id}"
        t_home = home_rec.get("targets", {}) or {}

        row = {
            "row_key": row_key,
            "match_id": match_id,
            "league": league,
            "season": season,
            "date": date,
            "time_GMT": home_rec.get("time_GMT"),
            "home_team_id": home_rec.get("team_id"),
            "home_team_name": home_rec.get("team_name"),
            "away_team_id": away_rec.get("team_id"),
            "away_team_name": away_rec.get("team_name"),
            # labels
            "home_goals": t_home.get("team_goals"),
            "away_goals": t_home.get("opponent_goals"),
            "btts": t_home.get("btts"),
            "over25": t_home.get("over25"),
        }

        # Optional helper target
        hg, ag = row["home_goals"], row["away_goals"]
        row["home_not_win"] = None
        if hg is not None and ag is not None:
            try:
                row["home_not_win"] = 1 if float(hg) - float(ag) <= 0 else 0
            except Exception:
                row["home_not_win"] = None

        # Build COMBO features (strict: every pair must exist on both sides)
        complete = True
        for s, sa in pairs:
            if s in hf and sa in aa and s in af and sa in ha:
                row[f"w5_combo_home_{s}"] = float(hf[s]) + float(aa[sa])
                row[f"w5_combo_away_{s}"] = float(af[s]) + float(ha[sa])
            else:
                complete = False
                break

        if not complete:
            skipped += 1
            continue

        rows[row_key] = row
        kept += 1

    print(f"[ROLLING_SIMPLE_NO_VENUE] kept={kept} skipped={skipped}")
    return rows


if __name__ == "__main__":
    out = build_window()
    # tiny preview
    # print(json.dumps(list(out.values())[:3], indent=2, ensure_ascii=False))
    print(json.dumps(out, indent=2))