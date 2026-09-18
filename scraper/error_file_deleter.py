import os
from send2trash import send2trash
from pathlib import Path
from scraper.file_checker import scan_matches
from src.paths import FBREF_RAW_MATCH
def trash_files(problematic_paths, dry_run=False):
    trashed = 0
    for fp in problematic_paths:
        p = Path(fp)
        if not p.exists():
            print("⚠️ missing:", p)
            continue
        if dry_run:
            print(f"[DRY] would send to trash → {p}")
        else:
            send2trash(str(p))
            print(f"trashed → {p}")
            trashed += 1
    print(f"done. trashed={trashed} (dry_run={dry_run})")
def main():
    root_folder = FBREF_RAW_MATCH
    all_matches = []
    for root, dir, files in os.walk(root_folder):
        for file in files:
            if file.endswith(".json"):
                all_matches.append(os.path.join(root, file))

    error_matches = scan_matches(all_matches)
    # print(error_matches)
    trash_files(error_matches)

if __name__ == "__main__":
    main()
