"""
Step 4 — Split Isan students into ขอนแก่น vs non-ขอนแก่น.

Reads:  isan_students.csv  (produced by step3_filter_non_isan.py)
Writes:
  - kk_students.csv      : students from ขอนแก่น
  - non_kk_isan_students.csv : Isan students NOT from ขอนแก่น

Detection uses both CSV province columns AND raw JSON alias keywords,
same approach as step 3.
"""

import csv
import json
import os
from glob import glob

INPUT_FILE     = "isan_students.csv"
KK_FILE        = "kk_students.csv"
NON_KK_FILE    = "non_kk_isan_students.csv"
SERPER_DIR     = "serper_results"
MAX_SCHOOLS    = 5

# ขอนแก่น keywords (partial forms people actually write in Thai text)
KK_ALIASES = ["ขอนแก่น", "ขอนแก่"]


def json_path_for(row_num):
    matches = glob(os.path.join(SERPER_DIR, f"{int(row_num):04d}_*.json"))
    return matches[0] if matches else None


def raw_text_from_json(path):
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""
    parts = []
    for key in ("school_background", "achievements"):
        for item in data.get("results", {}).get(key, {}).get("organic", []):
            parts.append(item.get("title", ""))
            parts.append(item.get("snippet", ""))
    return " ".join(parts)


def is_kk(row: dict) -> tuple:
    """Return (True, reason) if student is from ขอนแก่น."""
    # 1. Check province columns in CSV
    for i in range(1, MAX_SCHOOLS + 1):
        prov = row.get(f"province_{i}", "").strip()
        if prov == "ขอนแก่น":
            return True, f"CSV province_{i}: ขอนแก่น"

    # 2. If no provinces in CSV, scan raw JSON text with aliases
    if not any(row.get(f"province_{i}", "").strip() for i in range(1, MAX_SCHOOLS + 1)):
        jpath = json_path_for(row.get("row", 0))
        if jpath:
            text = raw_text_from_json(jpath)
            for alias in KK_ALIASES:
                if alias in text:
                    return True, f"alias match: {alias}"

    return False, "no ขอนแก่น indicator"


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"'{INPUT_FILE}' not found. Run step3_filter_non_isan.py first.")
        return

    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)

    kk_rows, non_kk_rows = [], []

    for row in all_rows:
        found, reason = is_kk(row)
        if found:
            kk_rows.append(row)
        else:
            non_kk_rows.append(row)
            print(f"  NON-KK  {row['clean_name']:<28}  ({reason})")

    def write_csv(path, rows):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    write_csv(KK_FILE,     kk_rows)
    write_csv(NON_KK_FILE, non_kk_rows)

    total = len(all_rows)
    print(f"\nTotal Isan students : {total}")
    print(f"  ขอนแก่น          : {len(kk_rows):<4}  → {KK_FILE}")
    print(f"  Other Isan        : {len(non_kk_rows):<4}  → {NON_KK_FILE}")


if __name__ == "__main__":
    main()
