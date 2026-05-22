"""
Step 5 — Summary report across all student categories.

Reads:
  - student_school_summary.csv  (all students)
  - kk_students.csv             (ขอนแก่น)
  - non_kk_isan_students.csv    (other Isan provinces)
  - non_isan_students.csv       (non-Isan)

Saves a Markdown report to summary_report.md.
"""

import csv
import os
from collections import Counter

MAX_SCHOOLS = 5

FILES = {
    "all":      "student_school_summary.csv",
    "kk":       "kk_students.csv",
    "non_kk":   "non_kk_isan_students.csv",
    "non_isan": "non_isan_students.csv",
}

ISAN_PROVINCES = {
    "กาฬสินธุ์", "ขอนแก่น", "ชัยภูมิ", "นครพนม", "นครราชสีมา",
    "บึงกาฬ", "บุรีรัมย์", "มหาสารคาม", "มุกดาหาร", "ยโสธร",
    "ร้อยเอ็ด", "เลย", "ศรีสะเกษ", "สกลนคร", "สุรินทร์",
    "หนองคาย", "หนองบัวลำภู", "อำนาจเจริญ", "อุดรธานี", "อุบลราชธานี",
}


def load_csv(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def get_provinces(row):
    """Return all non-empty province values for a row."""
    return [
        row[f"province_{i}"]
        for i in range(1, MAX_SCHOOLS + 1)
        if row.get(f"province_{i}", "").strip()
    ]


def get_primary_province(row):
    """Return the first non-empty province, or empty string."""
    for i in range(1, MAX_SCHOOLS + 1):
        p = row.get(f"province_{i}", "").strip()
        if p:
            return p
    return ""


def get_primary_school(row):
    return row.get("school_1", "").strip()


def province_counter(rows):
    """Count students by their first detected province."""
    c = Counter()
    for r in rows:
        p = get_primary_province(r)
        c[p or "(ไม่ทราบ)"] += 1
    return c


def school_counter(rows):
    """Count students by their first school."""
    c = Counter()
    for r in rows:
        s = get_primary_school(r)
        c[s or "(ไม่ทราบ)"] += 1
    return c


def md_table(headers, rows):
    """Render a simple Markdown table."""
    sep = "| " + " | ".join("---" for _ in headers) + " |"
    head = "| " + " | ".join(headers) + " |"
    body = ["| " + " | ".join(str(c) for c in row) + " |" for row in rows]
    return "\n".join([head, sep] + body)


def counter_table(counter, top, col_name):
    rows = [(name, count) for name, count in counter.most_common(top)]
    return md_table([col_name, "จำนวน (คน)"], rows)


def build_report(data):
    all_rows      = data["all"]
    kk_rows       = data["kk"]
    non_kk_rows   = data["non_kk"]
    non_isan_rows = data["non_isan"]

    total      = len(all_rows)
    n_kk       = len(kk_rows)
    n_non_kk   = len(non_kk_rows)
    n_non_isan = len(non_isan_rows)
    n_isan     = n_kk + n_non_kk

    lines = []
    lines.append("# รายงานสรุปนักศึกษาแพทย์ MD KKU\n")

    # Overview table
    lines.append("## ภาพรวม\n")
    lines.append(md_table(
        ["กลุ่ม", "จำนวน (คน)", "ร้อยละ"],
        [
            ("นักศึกษาทั้งหมด",     total,     "100.0%"),
            ("ภาคอีสาน (รวม)",      n_isan,    f"{n_isan/total*100:.1f}%"),
            ("- ขอนแก่น",           n_kk,      f"{n_kk/total*100:.1f}%"),
            ("- อีสานจังหวัดอื่น", n_non_kk,  f"{n_non_kk/total*100:.1f}%"),
            ("นอกภาคอีสาน",        n_non_isan, f"{n_non_isan/total*100:.1f}%"),
        ]
    ))

    # KK schools
    lines.append(f"\n## โรงเรียนของนักศึกษาจาก ขอนแก่น (top 10) - {n_kk} คน\n")
    lines.append(counter_table(school_counter(kk_rows), 10, "โรงเรียน"))

    # Other Isan by province
    lines.append(f"\n## อีสานจังหวัดอื่น - จำแนกตามจังหวัด (top 15) - {n_non_kk} คน\n")
    lines.append(counter_table(province_counter(non_kk_rows), 15, "จังหวัด"))

    # Other Isan top schools
    lines.append(f"\n## โรงเรียนของนักศึกษาอีสานจังหวัดอื่น (top 10)\n")
    lines.append(counter_table(school_counter(non_kk_rows), 10, "โรงเรียน"))

    # Non-Isan by province
    lines.append(f"\n## นอกภาคอีสาน - จำแนกตามจังหวัด - {n_non_isan} คน\n")
    lines.append(counter_table(province_counter(non_isan_rows), 20, "จังหวัด"))

    # Rosters
    lines.append("\n## รายชื่อนักศึกษาจาก ขอนแก่น\n")
    lines.append(md_table(
        ["#", "ชื่อ-นามสกุล", "โรงเรียน"],
        [(i, r["clean_name"], get_primary_school(r)) for i, r in enumerate(kk_rows, 1)]
    ))

    lines.append("\n## รายชื่อนักศึกษาอีสาน (ไม่ใช่ขอนแก่น)\n")
    lines.append(md_table(
        ["#", "ชื่อ-นามสกุล", "โรงเรียน", "จังหวัด"],
        [(i, r["clean_name"], get_primary_school(r), get_primary_province(r))
         for i, r in enumerate(non_kk_rows, 1)]
    ))

    lines.append("\n## รายชื่อนักศึกษานอกภาคอีสาน\n")
    lines.append(md_table(
        ["#", "ชื่อ-นามสกุล", "โรงเรียน", "จังหวัด"],
        [(i, r["clean_name"], get_primary_school(r), get_primary_province(r))
         for i, r in enumerate(non_isan_rows, 1)]
    ))

    return "\n".join(lines)


def main():
    missing = [k for k, v in FILES.items() if not os.path.exists(v)]
    if missing:
        print(f"Missing files: {[FILES[k] for k in missing]}")
        print("Please run steps 1–4 first.")
        return

    data = {key: load_csv(path) for key, path in FILES.items()}

    report = build_report(data)

    output_path = "summary_report.md"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"Report saved → {output_path}")


if __name__ == "__main__":
    main()
