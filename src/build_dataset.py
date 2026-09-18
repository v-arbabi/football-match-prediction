# src/build_dataset.py
# ---------------------------------------------------------------------
# Convert flat, per-match rolling output into training_table.csv.
# - Input: dict[row_key -> flat dict] from rolling.build_window()
# - Header = keys of the first row (order already set in rolling)
# - None values -> "" (empty string)
# ---------------------------------------------------------------------

import os
import csv

from src.rolling import build_window as build_rows
from src.config import DATA_PROCESSED_DIR as CSV_PATH


def _to_cell(value):
    """Keep numbers/strings as-is, convert None to empty string."""
    return "" if value is None else value


def write_csv(rows_dict, out_csv_path, encoding="utf-8"):
    if not rows_dict:
        raise ValueError("rows_dict is empty")

    # Header comes from first row's keys (insertion order preserved)
    first_row = next(iter(rows_dict.values()))
    header = list(first_row.keys())

    os.makedirs(os.path.dirname(out_csv_path) or ".", exist_ok=True)

    with open(out_csv_path, "w", newline="", encoding=encoding) as f:
        writer = csv.writer(f)
        writer.writerow(header)
        for row in rows_dict.values():
            if any(row.get(col) is None for col in header if col.startswith("w5_combo_")):
                continue  # skip this row
            writer.writerow([_to_cell(row.get(col)) for col in header])

    print(f"[build_training_csv] wrote {len(rows_dict)} rows → {out_csv_path}")


def main():
    out_csv_path = os.path.join(CSV_PATH, "training_table.csv")
    rows = build_rows()              # host-centric rolling output
    write_csv(rows, out_csv_path)


if __name__ == "__main__":
    main()