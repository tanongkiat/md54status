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
    "is_isan", "is_kk", "is_non_isan", "is_non_kk_isan",
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
    filter_tag = request.args.get("filter")  # all | isan | kk | non_isan | non_kk_isan
    search = request.args.get("search", "").strip()

    query = "SELECT * FROM students WHERE 1=1"
    params = []

    filter_map = {
        "isan": "is_isan",
        "kk": "is_kk",
        "non_isan": "is_non_isan",
        "non_kk_isan": "is_non_kk_isan",
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
    total = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    isan = conn.execute("SELECT COUNT(*) FROM students WHERE is_isan=1").fetchone()[0]
    kk = conn.execute("SELECT COUNT(*) FROM students WHERE is_kk=1").fetchone()[0]
    non_isan = conn.execute("SELECT COUNT(*) FROM students WHERE is_non_isan=1").fetchone()[0]
    non_kk_isan = conn.execute("SELECT COUNT(*) FROM students WHERE is_non_kk_isan=1").fetchone()[0]
    conn.close()
    return jsonify({
        "total": total, "isan": isan, "kk": kk,
        "non_isan": non_isan, "non_kk_isan": non_kk_isan,
    })


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


if __name__ == "__main__":
    # Auto-init DB if not present
    if not os.path.exists(DB_PATH):
        from init_db import init_db
        init_db()
    app.run(debug=True, port=5050)
