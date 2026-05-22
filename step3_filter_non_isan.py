"""
Step 3 — Filter students NOT from Northeast Thailand (Isan).

Reads:  student_school_summary.csv  (produced by step2_extract_school.py)
        serper_results/*.json        (for fallback text search on uncertain rows)
Writes:
  - isan_students.csv     : students with at least one Isan indicator found
  - non_isan_students.csv : everyone else (including those with no province at all)

Classification order:
  1. Check province_1…province_N in the CSV (exact Isan province names).
  2. If no province found, scan the raw JSON snippets using partial/alias keywords
     (e.g. "อุดร" → อุดรธานี, "สกล" → สกลนคร).
  3. If still nothing Isan → classify as non-Isan (assume non-Isan when unknown).
"""

import csv
import json
import os
import re
from glob import glob

INPUT_FILE    = "student_school_summary.csv"
SERPER_DIR    = "serper_results"
ISAN_FILE     = "isan_students.csv"
NON_ISAN_FILE = "non_isan_students.csv"
MAX_SCHOOLS   = 5   # must match step2 setting

# ── Isan province aliases ──────────────────────────────────────────────────────
# Key   = canonical province name
# Value = list of keywords (longest/most-specific first) that uniquely identify
#         this province in raw Thai text. Short forms are chosen to avoid
#         false-positive matches with non-Isan text.
ISAN_ALIASES: dict[str, list[str]] = {
    "กาฬสินธุ์":     ["กาฬสินธุ์", "กาฬ"],
    "ขอนแก่น":       ["ขอนแก่น","แก่น","ขอน"],
    "ชัยภูมิ":       ["ชัยภูมิ"],
    "นครพนม":        ["นครพนม"],
    "นครราชสีมา":    ["นครราชสีมา", "โคราช", "ราชสีมา"],
    "บึงกาฬ":        ["บึงกาฬ"],
    "บุรีรัมย์":     ["บุรีรัมย์"],
    "มหาสารคาม":     ["มหาสารคาม", "สารคาม"],
    "มุกดาหาร":      ["มุกดาหาร", "มุกดา"],
    "ยโสธร":         ["ยโสธร","ยโส"],
    "ร้อยเอ็ด":      ["ร้อยเอ็ด"],
    "เลย":           ["จ.เลย", "เลย"],   # prefix "จ." reduces false positives
    "ศรีสะเกษ":      ["ศรีสะเกษ"],
    "สกลนคร":        ["สกลนคร", "สกล"],
    "สุรินทร์":      ["สุรินทร์"],
    "หนองคาย":       ["หนองคาย"],
    "หนองบัวลำภู":   ["หนองบัวลำภู", "หนองบัว"],
    "อำนาจเจริญ":    ["อำนาจเจริญ", "อำนาจ"],
    "อุดรธานี":      ["อุดรธานี", "อุดร"],
    "อุบลราชธานี":   ["อุบลราชธานี", "อุบล"],
}

# Flat set of canonical names for quick CSV-province lookup
ISAN_PROVINCES = set(ISAN_ALIASES.keys())
# ──────────────────────────────────────────────────────────────────────────────


def isan_in_csv_provinces(row: dict) -> bool:
    """Return True if any province_N column is an Isan province."""
    for i in range(1, MAX_SCHOOLS + 1):
        prov = row.get(f"province_{i}", "").strip()
        if prov in ISAN_PROVINCES:
            return True
    return False


def has_any_province(row: dict) -> bool:
    """Return True if at least one province_N is non-empty."""
    return any(row.get(f"province_{i}", "").strip() for i in range(1, MAX_SCHOOLS + 1))


def json_path_for(row_num: int, clean_name: str):
    """Find the JSON file for this student in SERPER_DIR."""
    pattern = os.path.join(SERPER_DIR, f"{int(row_num):04d}_*.json")
    matches = glob(pattern)
    return matches[0] if matches else None


def raw_text_from_json(path: str) -> str:
    """Concatenate all titles + snippets from a Serper JSON file."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return ""
    parts = []
    for key in ("school_background", "achievements"):
        result = data.get("results", {}).get(key, {})
        for item in result.get("organic", []):
            parts.append(item.get("title", ""))
            parts.append(item.get("snippet", ""))
    return " ".join(parts)


def isan_in_raw_text(text: str) -> tuple[bool, str]:
    """
    Search raw text for any Isan alias keyword.
    Returns (found, matched_province_name).
    """
    for province, aliases in ISAN_ALIASES.items():
        for alias in aliases:
            if alias in text:
                return True, province
    return False, ""


def classify(row: dict) -> tuple[str, str]:
    """
    Return ('isan'|'non_isan', reason_string).

    Priority:
      1. Province columns in CSV
      2. Alias scan of raw JSON text
      3. Default → non_isan
    """
    # 1. Check CSV province columns
    if isan_in_csv_provinces(row):
        provinces = [
            row[f"province_{i}"]
            for i in range(1, MAX_SCHOOLS + 1)
            if row.get(f"province_{i}", "").strip() in ISAN_PROVINCES
        ]
        return "isan", f"CSV province: {provinces[0]}"

    # 2. If province columns are empty, scan raw JSON with aliases
    if not has_any_province(row):
        jpath = json_path_for(row.get("row", 0), row.get("clean_name", ""))
        if jpath:
            text = raw_text_from_json(jpath)
            found, prov = isan_in_raw_text(text)
            if found:
                return "isan", f"alias match: {prov}"

    # 3. Default: non-Isan (includes uncertain)
    return "non_isan", "no Isan indicator found"


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"'{INPUT_FILE}' not found. Run step2_extract_school.py first.")
        return

    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)

    isan_rows, non_isan_rows = [], []

    for row in all_rows:
        label, reason = classify(row)
        row["_reason"] = reason          # temporary, not written to CSV
        if label == "isan":
            isan_rows.append(row)
        else:
            non_isan_rows.append(row)
            print(f"  NON-ISAN  {row['clean_name']:<28}  ({reason})")

    def write_csv(path, rows):
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for r in rows:
                r.pop("_reason", None)
                writer.writerow(r)

    write_csv(ISAN_FILE,     isan_rows)
    write_csv(NON_ISAN_FILE, non_isan_rows)

    # Remove old uncertain file if it exists
    if os.path.exists("uncertain_students.csv"):
        os.remove("uncertain_students.csv")

    total = len(all_rows)
    print(f"\nTotal students : {total}")
    print(f"  Isan         : {len(isan_rows):<4}  → {ISAN_FILE}")
    print(f"  Non-Isan     : {len(non_isan_rows):<4}  → {NON_ISAN_FILE}")
    print("  (Uncertain rows are now classified as Non-Isan by default)")


if __name__ == "__main__":
    main()

