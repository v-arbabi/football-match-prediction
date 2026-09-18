import os
import json
import csv
from collections import defaultdict
from typing import Tuple, List, Dict, Any

# -------- Core per-file validator --------

def validate_match(filepath: str) -> Tuple[bool, List[str]]:
    """
    Validate a single match file.
    Returns:
        has_error (bool): True if any issue found
        issues (list[str]): list of issue codes/messages
    """
    issues = []

    # Load JSON
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)
            meta = data.get("meta_data", {})
    except Exception as e:
        issues.append(f"FILE_READ_ERROR: {e}")
        return True, issues
    # print(data)


    # Helper to push issues
    def add_issue(code: str):
        issues.append(code)

    # Check both sides
    for side in ["home", "away"]:
        side_block = data.get(side)
        if not side_block:
            add_issue(f"MISSING_SIDE:{side}")
            continue

        team_name = side_block.get("team_name")
        team_id   = side_block.get("team_id")
        lineup    = side_block.get("lineup", [])
        pstats    = side_block.get("players_stat", {})  # dict: pid -> info/stats

        # A) meta_data alignment (if provided)
        meta_side_id = meta.get(f"{side}_id")
        if meta_side_id is not None and team_id is not None and meta_side_id != team_id:
            add_issue(f"META_TEAM_ID_MISMATCH:{side}")

        # Build quick maps
        lineup_info = {p.get("player_id"): p for p in lineup if p.get("player_id")}
        pstats_team_id = {pid: block.get("information", {}).get("team_id")
                          for pid, block in pstats.items()}

        # B) players_stat team_id alignment (for present stats)
        for pid, p_tid in pstats_team_id.items():
            # If team_id missing in either side, skip hard fail (treat as soft issue)
            if team_id is None or p_tid is None:
                continue
            if p_tid != team_id:
                add_issue(f"PSTATS_TEAM_ID_MISMATCH:{side}:{pid}")

        # C) Who must have stats? (starters + subs who came in)
        must_have_stats = set()
        for pid, p in lineup_info.items():
            is_starter = bool(p.get("is_starter"))
            is_subbed_in = bool(p.get("is_substituted")) and not is_starter
            if is_starter or is_subbed_in:
                must_have_stats.add(pid)

        # D) Missing stats for those who actually played
        for pid in must_have_stats:
            if pid not in pstats:
                add_issue(f"MISSING_STATS_FOR_PLAYER:{side}:{pid}")

        # E) Lineup team_id alignment (if lineup records have team_id field)
        for pid, p in lineup_info.items():
            p_lineup_tid = p.get("team_id")
            if p_lineup_tid is not None and team_id is not None and p_lineup_tid != team_id:
                add_issue(f"LINEUP_TEAM_ID_MISMATCH:{side}:{pid}")

    return (len(issues) > 0), issues


# -------- Batch runner + reporting --------

def scan_matches(filepaths: List[str], report_csv_path: str = "validation_report.csv"):
    """
    Run validator on many files and produce:
      - aggregated counts per issue category
      - sample files per issue category
      - a CSV report (file, has_error, issues joined)
    """
    issue_counts: Dict[str, int] = defaultdict(int)
    issue_samples: Dict[str, List[str]] = defaultdict(list)

    total = 0
    total_with_errors = 0

    # Prepare CSV
    rows = []
    error_matches_list = []
    for fp in filepaths:
        total += 1
        has_error, issues = validate_match(fp)

        if has_error:
            total_with_errors += 1
            error_matches_list.append(fp)
        # Aggregate
        if issues:
            # also store samples (limit to a few per issue to avoid huge memory)
            for code in issues:
                issue_counts[code] += 1
                if len(issue_samples[code]) < 5:
                    issue_samples[code].append(fp)

        rows.append({
            "file": fp,
            "has_error": int(has_error),
            "issues": "|".join(issues) if issues else ""
        })

    # Write CSV
    fieldnames = ["file", "has_error", "issues"]
    with open(report_csv_path, "w", newline="", encoding="utf-8") as outf:
        writer = csv.DictWriter(outf, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Print summary
    error_rate = (total_with_errors / total * 100.0) if total else 0.0
    print(f"\nProcessed: {total} files")
    print(f"Files with errors: {total_with_errors} ({error_rate:.1f}%)")
    print("\nTop issues:")
    for code, cnt in sorted(issue_counts.items(), key=lambda x: x[1], reverse=True):
        print(f"  {code}: {cnt}")
        # show a few sample files for this issue
        for smp in issue_samples[code]:
            print(f"    - {smp}")
    print(f"\nCSV report saved to: {report_csv_path}")

    return error_matches_list
# -------- Example usage --------
# Collect your json files however you prefer:
# filepaths = [...]
# scan_matches(filepaths, report_csv_path="validation_report.csv")



def main():
    root_folder = "/Users/valiollaharbabi/PycharmProjects/footbal_prediction_project/data/raw/fbref"
    all_matches = []
    for root, dir, files in os.walk(root_folder):
        for file in files:
            if file.endswith(".json"):
                all_matches.append(os.path.join(root, file))

    error_matches = scan_matches(all_matches)
    print(error_matches)

if __name__ == "__main__":
    main()
