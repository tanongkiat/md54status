"""
Recompute all flag columns from province_1 (primary school province).
Run: python3 recompute_flags.py
Also called automatically by init_db and the Render build step.
"""

import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "students.db")

ISAN_PROVINCES = {
    "กาฬสินธุ์", "ขอนแก่น", "ชัยภูมิ", "นครพนม", "นครราชสีมา",
    "บึงกาฬ", "บุรีรัมย์", "มหาสารคาม", "มุกดาหาร", "ยโสธร",
    "ร้อยเอ็ด", "เลย", "ศรีสะเกษ", "สกลนคร", "สุรินทร์",
    "หนองคาย", "หนองบัวลำภู", "อำนาจเจริญ", "อุดรธานี", "อุบลราชธานี",
}

BKK_PROVINCES = {
    "กรุงเทพมหานคร", "นนทบุรี", "ปทุมธานี",
    "สมุทรปราการ", "นครปฐม", "สมุทรสาคร",
}


def recompute(conn=None):
    close_after = conn is None
    if conn is None:
        conn = sqlite3.connect(DB_PATH)

    cur = conn.cursor()

    # Add is_bkk column if missing
    cols = {r[1] for r in cur.execute("PRAGMA table_info(students)").fetchall()}
    if "is_bkk" not in cols:
        cur.execute("ALTER TABLE students ADD COLUMN is_bkk INTEGER DEFAULT 0")

    rows = cur.execute("SELECT row, province_1 FROM students").fetchall()
    for row_id, prov in rows:
        p = (prov or "").strip()
        is_isan        = 1 if p in ISAN_PROVINCES else 0
        is_kk          = 1 if p == "ขอนแก่น" else 0
        is_non_isan    = 1 if p and p not in ISAN_PROVINCES else 0
        is_non_kk_isan = 1 if p in ISAN_PROVINCES and p != "ขอนแก่น" else 0
        is_bkk         = 1 if p in BKK_PROVINCES else 0

        cur.execute("""
            UPDATE students
            SET is_isan=?, is_kk=?, is_non_isan=?, is_non_kk_isan=?, is_bkk=?
            WHERE row=?
        """, (is_isan, is_kk, is_non_isan, is_non_kk_isan, is_bkk, row_id))

    conn.commit()
    if close_after:
        conn.close()
    print(f"Recomputed flags for {len(rows)} students.")


if __name__ == "__main__":
    recompute()
