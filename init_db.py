"""
Initialize SQLite database from CSV files.
Base table: student_school_summary.csv (268 students with school info)
Extra info: student_school_info.csv (school_background, achievements for some rows)
Flags: isan_students, kk_students, non_isan_students, non_kk_isan_students
"""

import csv
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "students.db")
BASE_DIR = os.path.dirname(__file__)


def read_csv_rows(filename):
    path = os.path.join(BASE_DIR, filename)
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def get_row_set(filename):
    rows = read_csv_rows(filename)
    return {int(r["row"]) for r in rows}


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Create main students table
    cur.execute("DROP TABLE IF EXISTS students")
    cur.execute("""
        CREATE TABLE students (
            row         INTEGER PRIMARY KEY,
            full_name   TEXT,
            clean_name  TEXT,
            school_1    TEXT,
            province_1  TEXT,
            school_2    TEXT,
            province_2  TEXT,
            school_3    TEXT,
            province_3  TEXT,
            school_4    TEXT,
            province_4  TEXT,
            school_5    TEXT,
            province_5  TEXT,
            school_background TEXT,
            achievements TEXT,
            is_isan     INTEGER DEFAULT 0,
            is_kk       INTEGER DEFAULT 0,
            is_non_isan INTEGER DEFAULT 0,
            is_non_kk_isan INTEGER DEFAULT 0
        )
    """)

    # Load base data from student_school_summary.csv
    base_rows = read_csv_rows("student_school_summary.csv")
    for r in base_rows:
        cur.execute("""
            INSERT INTO students (row, full_name, clean_name,
                school_1, province_1, school_2, province_2,
                school_3, province_3, school_4, province_4,
                school_5, province_5)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            int(r["row"]), r.get("full_name", ""), r.get("clean_name", ""),
            r.get("school_1", ""), r.get("province_1", ""),
            r.get("school_2", ""), r.get("province_2", ""),
            r.get("school_3", ""), r.get("province_3", ""),
            r.get("school_4", ""), r.get("province_4", ""),
            r.get("school_5", ""), r.get("province_5", ""),
        ))

    # Merge extra info from student_school_info.csv
    info_rows = read_csv_rows("student_school_info.csv")
    for r in info_rows:
        cur.execute("""
            UPDATE students SET school_background=?, achievements=?
            WHERE row=?
        """, (r.get("school_background", ""), r.get("achievements", ""), int(r["row"])))

    # Apply filter flags
    isan_set         = get_row_set("isan_students.csv")
    kk_set           = get_row_set("kk_students.csv")
    non_isan_set     = get_row_set("non_isan_students.csv")
    non_kk_isan_set  = get_row_set("non_kk_isan_students.csv")

    for row_id in isan_set:
        cur.execute("UPDATE students SET is_isan=1 WHERE row=?", (row_id,))
    for row_id in kk_set:
        cur.execute("UPDATE students SET is_kk=1 WHERE row=?", (row_id,))
    for row_id in non_isan_set:
        cur.execute("UPDATE students SET is_non_isan=1 WHERE row=?", (row_id,))
    for row_id in non_kk_isan_set:
        cur.execute("UPDATE students SET is_non_kk_isan=1 WHERE row=?", (row_id,))

    conn.commit()
    conn.close()

    print(f"Database created at {DB_PATH}")
    print(f"  students: {len(base_rows)} rows")
    print(f"  extra info merged: {len(info_rows)} rows")
    print(f"  isan: {len(isan_set)}, kk: {len(kk_set)}, non_isan: {len(non_isan_set)}, non_kk_isan: {len(non_kk_isan_set)}")


if __name__ == "__main__":
    init_db()
