"""
Import students_export.csv back into students.db
Usage: python3 import_csv_to_db.py [path/to/students_export.csv]
"""

import csv
import sqlite3
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "students.db")

COL_MAP = {
    "#":          "row",
    "ชื่อเต็ม":    "full_name",
    "Clean":      "clean_name",
    "โรงเรียน 1": "school_1",
    "จังหวัด 1":  "province_1",
    "โรงเรียน 2": "school_2",
    "จังหวัด 2":  "province_2",
    "โรงเรียน 3": "school_3",
    "จังหวัด 3":  "province_3",
    "โรงเรียน 4": "school_4",
    "จังหวัด 4":  "province_4",
    "โรงเรียน 5": "school_5",
    "จังหวัด 5":  "province_5",
    "อีสาน":      "is_isan",
    "ขก":         "is_kk",
    "นอกอีสาน":   "is_non_isan",
    "อีสาน¬ขก":  "is_non_kk_isan",
}

FLAG_COLS = {"is_isan", "is_kk", "is_non_isan", "is_non_kk_isan"}


def import_csv(csv_path: str):
    if not os.path.exists(csv_path):
        print(f"File not found: {csv_path}")
        sys.exit(1)

    with open(csv_path, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    if not rows:
        print("CSV is empty.")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute("DROP TABLE IF EXISTS students")
    cur.execute("""
        CREATE TABLE students (
            row              INTEGER PRIMARY KEY,
            full_name        TEXT,
            clean_name       TEXT,
            school_1         TEXT,
            province_1       TEXT,
            school_2         TEXT,
            province_2       TEXT,
            school_3         TEXT,
            province_3       TEXT,
            school_4         TEXT,
            province_4       TEXT,
            school_5         TEXT,
            province_5       TEXT,
            school_background TEXT,
            achievements      TEXT,
            is_isan          INTEGER DEFAULT 0,
            is_kk            INTEGER DEFAULT 0,
            is_non_isan      INTEGER DEFAULT 0,
            is_non_kk_isan   INTEGER DEFAULT 0
        )
    """)

    inserted = 0
    for r in rows:
        mapped = {}
        for thai_col, db_col in COL_MAP.items():
            val = r.get(thai_col, "")
            if db_col in FLAG_COLS:
                try:
                    val = int(val) if val.strip() else 0
                except ValueError:
                    val = 0
            mapped[db_col] = val

        if not mapped.get("row"):
            continue

        cur.execute("""
            INSERT OR REPLACE INTO students (
                row, full_name, clean_name,
                school_1, province_1, school_2, province_2,
                school_3, province_3, school_4, province_4,
                school_5, province_5,
                school_background, achievements,
                is_isan, is_kk, is_non_isan, is_non_kk_isan
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            int(mapped["row"]), mapped["full_name"], mapped["clean_name"],
            mapped["school_1"], mapped["province_1"],
            mapped["school_2"], mapped["province_2"],
            mapped["school_3"], mapped["province_3"],
            mapped["school_4"], mapped["province_4"],
            mapped["school_5"], mapped["province_5"],
            "", "",  # school_background / achievements not in export CSV
            mapped["is_isan"], mapped["is_kk"],
            mapped["is_non_isan"], mapped["is_non_kk_isan"],
        ))
        inserted += 1

    conn.commit()
    conn.close()
    print(f"Done. {inserted} students imported into {DB_PATH}")


if __name__ == "__main__":
    csv_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join(BASE_DIR, "students_export.csv")
    import_csv(csv_path)
