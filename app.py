"""
Flask server for MD KKU Student Browser & Editor
"""

import sqlite3
import os
import hmac
from functools import wraps
from flask import Flask, jsonify, request, render_template, abort, session, redirect, url_for, send_file

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "students.db")

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-me-in-production")

# Credentials – set LOGIN_USERNAME / LOGIN_PASSWORD env vars on Render
LOGIN_USERNAME = os.environ.get("LOGIN_USERNAME", "admin")
LOGIN_PASSWORD = os.environ.get("LOGIN_PASSWORD", "admin1234")


def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            if request.path.startswith("/api/"):
                return jsonify({"error": "unauthorized"}), 401
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated


EDITABLE_COLUMNS = [
    "full_name", "clean_name",
    "school_1", "province_1",
    "school_2", "province_2",
    "school_3", "province_3",
    "school_4", "province_4",
    "school_5", "province_5",
    "school_background", "achievements",
    "is_isan", "is_kk", "is_non_isan", "is_non_kk_isan", "is_bkk",
]


def get_db():
    if not os.path.exists(DB_PATH):
        from init_db import init_db
        init_db()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


# ── Routes ──────────────────────────────────────────────────────────────────

@app.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        # Use compare_digest to prevent timing attacks
        ok_user = hmac.compare_digest(username, LOGIN_USERNAME)
        ok_pass = hmac.compare_digest(password, LOGIN_PASSWORD)
        if ok_user and ok_pass:
            session["logged_in"] = True
            return redirect(url_for("index"))
        error = "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"
    return render_template("login.html", error=error)


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/")
@login_required
def index():
    return render_template("index.html")


@app.route("/api/students")
@login_required
def list_students():
    search = request.args.get("search", "").strip()
    filter_tag = request.args.get("filter", "all")

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    filter_map = {
        "isan":        "is_isan",
        "non_isan":    "is_non_isan",
        "kk":          "is_kk",
        "non_kk_isan": "is_non_kk_isan",
        "bkk":         "is_bkk",
    }
    if filter_tag in filter_map:
        query += f" AND {filter_map[filter_tag]}=1"

    if search:
        query += """ AND (
            full_name LIKE ? OR clean_name LIKE ?
            OR school_1 LIKE ? OR province_1 LIKE ?
            OR school_2 LIKE ? OR province_2 LIKE ?
            OR school_3 LIKE ? OR province_3 LIKE ?
            OR school_4 LIKE ? OR province_4 LIKE ?
            OR school_5 LIKE ? OR province_5 LIKE ?
            OR school_background LIKE ? OR achievements LIKE ?
        )"""
        params += [f"%{search}%"] * 14

    query += " ORDER BY row"

    conn = get_db()
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/students/<int:row_id>", methods=["GET"])
@login_required
def get_student(row_id):
    conn = get_db()
    row = conn.execute("SELECT * FROM students WHERE row=?", (row_id,)).fetchone()
    conn.close()
    if row is None:
        abort(404)
    return jsonify(dict(row))


@app.route("/api/students/<int:row_id>", methods=["PUT"])
@login_required
def update_student(row_id):
    data = request.get_json(force=True)
    if not data:
        abort(400)

    # Only allow known editable columns
    updates = {k: v for k, v in data.items() if k in EDITABLE_COLUMNS}
    if not updates:
        return jsonify({"ok": True, "message": "nothing to update"})

    set_clause = ", ".join(f"{col}=?" for col in updates)
    values = list(updates.values()) + [row_id]

    conn = get_db()
    conn.execute(f"UPDATE students SET {set_clause} WHERE row=?", values)
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/students/<int:row_id>/toggle/<string:flag>", methods=["POST"])
@login_required
def toggle_flag(row_id, flag):
    if flag not in ("is_isan", "is_kk", "is_non_isan", "is_non_kk_isan"):
        abort(400)
    conn = get_db()
    cur = conn.execute(f"SELECT {flag} FROM students WHERE row=?", (row_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        abort(404)
    new_val = 0 if row[0] else 1
    conn.execute(f"UPDATE students SET {flag}=? WHERE row=?", (new_val, row_id))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, flag: new_val})


@app.route("/api/stats")
@login_required
def stats():
    conn = get_db()
    def cnt(col):
        return conn.execute(f"SELECT COUNT(*) FROM students WHERE {col}=1").fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    result = {
        "total":        total,
        "isan":         cnt("is_isan"),
        "non_isan":     cnt("is_non_isan"),
        "kk":           cnt("is_kk"),
        "non_kk_isan":  cnt("is_non_kk_isan"),
        "bkk":          cnt("is_bkk"),
    }
    conn.close()
    return jsonify(result)


@app.route("/admin/recompute-flags", methods=["POST"])
@login_required
def recompute_flags_route():
    from recompute_flags import recompute
    conn = get_db()
    recompute(conn)
    conn.close()
    return jsonify({"ok": True})


@app.route("/admin/download-db")
@login_required
def download_db():
    """Download the live students.db (login required)."""
    if not os.path.exists(DB_PATH):
        abort(404)
    return send_file(DB_PATH, as_attachment=True, download_name="students.db")


@app.route("/admin/upload-csv", methods=["GET", "POST"])
@login_required
def upload_csv():
    """Upload a students_export.csv to rebuild the DB in place."""
    if request.method == "GET":
        return render_template("upload_csv.html")

    file = request.files.get("csvfile")
    if not file or not file.filename.endswith(".csv"):
        return render_template("upload_csv.html", error="กรุณาเลือกไฟล์ .csv")

    import csv as _csv
    from import_csv_to_db import COL_MAP, FLAG_COLS

    content = file.read().decode("utf-8-sig")
    reader = _csv.DictReader(content.splitlines())
    rows = list(reader)

    if not rows:
        return render_template("upload_csv.html", error="ไฟล์ว่างเปล่า")

    conn = get_db()
    cur = conn.cursor()
    inserted = 0
    for r in rows:
        mapped = {}
        for thai_col, db_col in COL_MAP.items():
            val = r.get(thai_col, "")
            if db_col in FLAG_COLS:
                try:
                    val = int(val) if str(val).strip() else 0
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
            "", "",
            mapped["is_isan"], mapped["is_kk"],
            mapped["is_non_isan"], mapped["is_non_kk_isan"],
        ))
        inserted += 1

    conn.commit()
    conn.close()
    return render_template("upload_csv.html", success=f"นำเข้าสำเร็จ {inserted} คน")


# ── Province → Region mapping ────────────────────────────────────────────────

PROVINCE_REGION = {
    # อีสาน
    "กาฬสินธุ์": "อีสาน", "ขอนแก่น": "อีสาน", "ชัยภูมิ": "อีสาน",
    "นครพนม": "อีสาน", "นครราชสีมา": "อีสาน", "บึงกาฬ": "อีสาน",
    "บุรีรัมย์": "อีสาน", "มหาสารคาม": "อีสาน", "มุกดาหาร": "อีสาน",
    "ยโสธร": "อีสาน", "ร้อยเอ็ด": "อีสาน", "เลย": "อีสาน",
    "ศรีสะเกษ": "อีสาน", "สกลนคร": "อีสาน", "สุรินทร์": "อีสาน",
    "หนองคาย": "อีสาน", "หนองบัวลำภู": "อีสาน", "อำนาจเจริญ": "อีสาน",
    "อุดรธานี": "อีสาน", "อุบลราชธานี": "อีสาน",
    # เหนือ
    "กำแพงเพชร": "เหนือ", "เชียงราย": "เหนือ", "เชียงใหม่": "เหนือ",
    "ตาก": "เหนือ", "น่าน": "เหนือ", "พะเยา": "เหนือ",
    "พิจิตร": "เหนือ", "พิษณุโลก": "เหนือ", "เพชรบูรณ์": "เหนือ",
    "แพร่": "เหนือ", "แม่ฮ่องสอน": "เหนือ", "ลำปาง": "เหนือ",
    "ลำพูน": "เหนือ", "สุโขทัย": "เหนือ", "อุตรดิตถ์": "เหนือ",
    "อุทัยธานี": "เหนือ", "นครสวรรค์": "เหนือ",
    # กลาง
    "กรุงเทพมหานคร": "กลาง", "กาญจนบุรี": "กลาง", "นครนายก": "กลาง",
    "นครปฐม": "กลาง", "นนทบุรี": "กลาง", "ปทุมธานี": "กลาง",
    "พระนครศรีอยุธยา": "กลาง", "ราชบุรี": "กลาง", "ลพบุรี": "กลาง",
    "สมุทรปราการ": "กลาง", "สมุทรสงคราม": "กลาง", "สมุทรสาคร": "กลาง",
    "สระบุรี": "กลาง", "สิงห์บุรี": "กลาง", "สุพรรณบุรี": "กลาง",
    "อ่างทอง": "กลาง", "ชัยนาท": "กลาง",
    # ตะวันออก
    "จันทบุรี": "ตะวันออก", "ฉะเชิงเทรา": "ตะวันออก", "ชลบุรี": "ตะวันออก",
    "ตราด": "ตะวันออก", "ปราจีนบุรี": "ตะวันออก", "ระยอง": "ตะวันออก",
    "สระแก้ว": "ตะวันออก",
    # ตะวันตก
    "ประจวบคีรีขันธ์": "ตะวันตก", "เพชรบุรี": "ตะวันตก",
    # ใต้
    "กระบี่": "ใต้", "ชุมพร": "ใต้", "ตรัง": "ใต้",
    "นครศรีธรรมราช": "ใต้", "นราธิวาส": "ใต้", "ปัตตานี": "ใต้",
    "พังงา": "ใต้", "พัทลุง": "ใต้", "ภูเก็ต": "ใต้",
    "ยะลา": "ใต้", "ระนอง": "ใต้", "สงขลา": "ใต้",
    "สตูล": "ใต้", "สุราษฎร์ธานี": "ใต้",
}

REGION_ORDER = ["อีสาน", "กลาง", "เหนือ", "ตะวันออก", "ตะวันตก", "ใต้", "ต่างประเทศ/อื่นๆ"]


@app.route("/dashboard")
@login_required
def dashboard():
    return render_template("dashboard.html")


@app.route("/api/dashboard")
@login_required
def api_dashboard():
    conn = get_db()

    # ── Region flags (from student-level flags) ──────────────────────────
    def cnt(col):
        return conn.execute(f"SELECT COUNT(*) FROM students WHERE {col}=1").fetchone()[0]

    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    flag_stats = {
        "ทั้งหมด": total,
        "อีสาน": cnt("is_isan"),
        "ขอนแก่น": cnt("is_kk"),
        "อีสาน (ไม่ใช่ ขก)": cnt("is_non_kk_isan"),
        "นอกอีสาน": cnt("is_non_isan"),
    }

    # ── Province counts (all 5 slots, primary school province only = slot 1) ─
    prov_rows = conn.execute("""
        SELECT province, COUNT(*) as cnt FROM (
            SELECT province_1 as province FROM students WHERE province_1 != '' AND province_1 IS NOT NULL
            UNION ALL SELECT province_2 FROM students WHERE province_2 != '' AND province_2 IS NOT NULL
            UNION ALL SELECT province_3 FROM students WHERE province_3 != '' AND province_3 IS NOT NULL
            UNION ALL SELECT province_4 FROM students WHERE province_4 != '' AND province_4 IS NOT NULL
            UNION ALL SELECT province_5 FROM students WHERE province_5 != '' AND province_5 IS NOT NULL
        ) GROUP BY province ORDER BY cnt DESC LIMIT 30
    """).fetchall()
    province_stats = [{"province": r[0], "count": r[1]} for r in prov_rows]

    # Province slot-1 only (primary school)
    prov1_rows = conn.execute("""
        SELECT province_1 as province, COUNT(*) as cnt FROM students
        WHERE province_1 != '' AND province_1 IS NOT NULL
        GROUP BY province_1 ORDER BY cnt DESC LIMIT 30
    """).fetchall()
    province1_stats = [{"province": r[0], "count": r[1]} for r in prov1_rows]

    # ── School counts ────────────────────────────────────────────────────
    school_rows = conn.execute("""
        SELECT school, COUNT(*) as cnt FROM (
            SELECT school_1 as school FROM students WHERE school_1 != '' AND school_1 IS NOT NULL
            UNION ALL SELECT school_2 FROM students WHERE school_2 != '' AND school_2 IS NOT NULL
            UNION ALL SELECT school_3 FROM students WHERE school_3 != '' AND school_3 IS NOT NULL
            UNION ALL SELECT school_4 FROM students WHERE school_4 != '' AND school_4 IS NOT NULL
            UNION ALL SELECT school_5 FROM students WHERE school_5 != '' AND school_5 IS NOT NULL
        ) GROUP BY school ORDER BY cnt DESC LIMIT 30
    """).fetchall()
    school_stats = [{"school": r[0], "count": r[1]} for r in school_rows]

    # ── Region aggregation from province data ────────────────────────────
    region_counts = {r: 0 for r in REGION_ORDER}
    for p in province_stats:
        region = PROVINCE_REGION.get(p["province"], "ต่างประเทศ/อื่นๆ")
        region_counts[region] = region_counts.get(region, 0) + p["count"]
    region_stats = [{"region": k, "count": v} for k, v in region_counts.items() if v > 0]

    conn.close()
    return jsonify({
        "flag_stats": flag_stats,
        "province_stats": province_stats,
        "province1_stats": province1_stats,
        "school_stats": school_stats,
        "region_stats": region_stats,
        "total": total,
    })


if __name__ == "__main__":
    # Auto-init DB if not present
    if not os.path.exists(DB_PATH):
        from init_db import init_db
        init_db()
    app.run(debug=True, port=5050)
