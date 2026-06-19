import csv
import os
import sqlite3
import sys


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "students.db")
INPUT_CSV = os.path.join(BASE_DIR, "MD54_Full.csv")
OUTPUT_CSV = os.path.join(BASE_DIR, "MD54_Full_enriched.csv")

HONORIFICS = (
    "นางสาว", "นาง", "นาย", "เด็กหญิง", "เด็กชาย",
    "ดร.", "ศ.", "รศ.", "ผศ.", "พ.ต.", "ร.ต.",
)

DB_COLUMNS = [
    "row",
    "full_name",
    "clean_name",
    "school_1",
    "province_1",
    "school_2",
    "province_2",
    "school_3",
    "province_3",
    "school_4",
    "province_4",
    "school_5",
    "province_5",
    "school_background",
    "achievements",
    "is_isan",
    "is_kk",
    "is_non_isan",
    "is_non_kk_isan",
    "is_bkk",
]


def normalize_spaces(value: str) -> str:
    return " ".join((value or "").replace("\xa0", " ").split())


def strip_honorific(name: str) -> str:
    clean = normalize_spaces(name)
    for honorific in HONORIFICS:
        if clean.startswith(honorific):
            return clean[len(honorific):].strip()
    return clean


def load_db_rows(db_path: str) -> tuple[dict[str, dict], dict[str, dict]]:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        f"SELECT {', '.join(DB_COLUMNS)} FROM students"
    ).fetchall()
    conn.close()

    by_full_name = {}
    by_clean_name = {}
    for row in rows:
        record = dict(row)
        full_name_key = normalize_spaces(record.get("full_name", ""))
        clean_name_key = normalize_spaces(record.get("clean_name", "")) or strip_honorific(full_name_key)
        if full_name_key and full_name_key not in by_full_name:
            by_full_name[full_name_key] = record
        if clean_name_key and clean_name_key not in by_clean_name:
            by_clean_name[clean_name_key] = record
    return by_full_name, by_clean_name


def detect_name_column(fieldnames: list[str]) -> str:
    normalized = {normalize_spaces(name): name for name in fieldnames}
    for candidate in ("ชื่อ", "ชื่อเต็ม", "full_name", "name"):
        if candidate in normalized:
            return normalized[candidate]
    raise KeyError("Could not find a student name column in the source CSV.")


def blank_db_payload() -> dict:
    return {column: "" for column in DB_COLUMNS}


def merge_csv(input_csv: str, output_csv: str, db_path: str) -> tuple[int, int]:
    if not os.path.exists(input_csv):
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")
    if not os.path.exists(db_path):
        raise FileNotFoundError(f"Database not found: {db_path}")

    by_full_name, by_clean_name = load_db_rows(db_path)

    with open(input_csv, encoding="utf-8-sig", newline="") as src:
        reader = csv.DictReader(src)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    if not rows or not fieldnames:
        raise ValueError("Input CSV is empty.")

    name_column = detect_name_column(fieldnames)
    output_fields = fieldnames + [column for column in DB_COLUMNS if column not in fieldnames]

    matched = 0
    unmatched = 0
    merged_rows = []

    for row in rows:
        full_name = normalize_spaces(row.get(name_column, ""))
        clean_name = strip_honorific(full_name)

        db_record = by_full_name.get(full_name) or by_clean_name.get(clean_name)
        payload = blank_db_payload()

        if db_record:
            payload.update({key: db_record.get(key, "") for key in DB_COLUMNS})
            matched += 1
        else:
            unmatched += 1

        merged = dict(row)
        merged.update(payload)
        merged_rows.append(merged)

    with open(output_csv, "w", encoding="utf-8-sig", newline="") as dst:
        writer = csv.DictWriter(dst, fieldnames=output_fields)
        writer.writeheader()
        writer.writerows(merged_rows)

    return matched, unmatched


def main() -> None:
    input_csv = sys.argv[1] if len(sys.argv) > 1 else INPUT_CSV
    output_csv = sys.argv[2] if len(sys.argv) > 2 else OUTPUT_CSV

    matched, unmatched = merge_csv(input_csv, output_csv, DB_PATH)
    print(f"Wrote: {output_csv}")
    print(f"Matched students: {matched}")
    print(f"Unmatched students: {unmatched}")


if __name__ == "__main__":
    main()