"""
Step 2 — Parse Serper JSON results and extract school names & provinces.

Reads:  serper_results/*.json  (produced by step1_fetch_serper.py)
Writes: student_school_summary.csv

Each unique school found is stored in its own column pair:
  school_1, province_1, school_2, province_2, ...  (up to MAX_SCHOOLS)

Schools are ranked by how many times they appear near the student's name,
with elementary schools (อนุบาล) ranked last.
Province for each school is found in the 120 chars immediately following
that school's mention in the text.
"""

import csv
import json
import os
import re
from collections import Counter, defaultdict
from glob import glob

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_DIR   = "serper_results"
OUTPUT_FILE = "student_school_summary.csv"
MAX_SCHOOLS = 5    # maximum school columns to output
# ──────────────────────────────────────────────────────────────────────────────

THAI_PROVINCES = [
    "กระบี่", "กาญจนบุรี", "กาฬสินธุ์", "กำแพงเพชร", "ขอนแก่น",
    "จันทบุรี", "ฉะเชิงเทรา", "ชลบุรี", "ชัยนาท", "ชัยภูมิ",
    "ชุมพร", "เชียงราย", "เชียงใหม่", "ตรัง", "ตราด",
    "ตาก", "นครนายก", "นครปฐม", "นครพนม", "นครราชสีมา",
    "นครศรีธรรมราช", "นครสวรรค์", "นนทบุรี", "นราธิวาส", "น่าน",
    "บึงกาฬ", "บุรีรัมย์", "ปทุมธานี", "ประจวบคีรีขันธ์", "ปราจีนบุรี",
    "ปัตตานี", "พระนครศรีอยุธยา", "พะเยา", "พังงา", "พัทลุง",
    "พิจิตร", "พิษณุโลก", "เพชรบุรี", "เพชรบูรณ์", "แพร่",
    "ภูเก็ต", "มหาสารคาม", "มุกดาหาร", "แม่ฮ่องสอน", "ยโสธร",
    "ยะลา", "ร้อยเอ็ด", "ระนอง", "ระยอง", "ราชบุรี",
    "ลพบุรี", "ลำปาง", "ลำพูน", "เลย", "ศรีสะเกษ",
    "สกลนคร", "สงขลา", "สตูล", "สมุทรปราการ", "สมุทรสงคราม",
    "สมุทรสาคร", "สระแก้ว", "สระบุรี", "สิงห์บุรี", "สุโขทัย",
    "สุพรรณบุรี", "สุราษฎร์ธานี", "สุรินทร์", "หนองคาย", "หนองบัวลำภู",
    "อ่างทอง", "อำนาจเจริญ", "อุดรธานี", "อุตรดิตถ์", "อุทัยธานี",
    "อุบลราชธานี", "กรุงเทพมหานคร", "กรุงเทพ",
]

# Tokens that mark the end of a school name
_SCHOOL_END = re.compile(
    r'\s*(?:สพม|สพป|ม\.|ป\.|จ\.|เขต|ผ่าน|ได้|ที่|และ|กับ|เพื่อ|โดย|ใน|จาก|,|;|\|)'
)

# Regex: โรงเรียน + up to 5 consecutive Thai words
_SCHOOL_RE = re.compile(
    r'โรงเรียน[\u0E00-\u0E7F]+(?:\s[\u0E00-\u0E7F]+){0,4}'
)


def extract_text_from_json(data: dict) -> str:
    """Concatenate all titles + snippets from both query results."""
    parts = []
    for key in ("school_background", "achievements"):
        result = data.get("results", {}).get(key, {})
        for item in result.get("organic", []):
            parts.append(item.get("title", ""))
            parts.append(item.get("snippet", ""))
    return " ".join(parts)


def clean_school_name(raw: str) -> str:
    """Trim a raw regex match at the first stop-token or non-Thai run."""
    name = _SCHOOL_END.split(raw)[0].strip()
    name = re.split(r'[a-zA-Z0-9]{4,}|[/\\(){}\[\]]', name)[0].strip()
    return name


def province_after(text: str, school: str) -> str:
    """Return province found in the 120 chars immediately after school name."""
    idx = text.find(school)
    while idx != -1:
        window = text[idx + len(school): idx + len(school) + 120]
        for prov in THAI_PROVINCES:
            if prov in window:
                return prov
        idx = text.find(school, idx + 1)
    return ""


def ranked_schools(text: str, clean_name: str) -> list[tuple[str, str]]:
    """
    Return a list of (school_name, province) tuples, deduplicated and ranked:
      1. Non-elementary schools closest to the student's name (by distance)
      2. Elementary schools last
    Each school appears only once (first/closest occurrence used for province).
    """
    name_positions = [m.start() for m in re.finditer(re.escape(clean_name), text)]

    # Gather all school matches with position and cleaned name
    matches = []
    for m in _SCHOOL_RE.finditer(text):
        name = clean_school_name(m.group())
        if len(name) <= 8:
            continue
        is_elem = "อนุบาล" in name
        # Minimum distance to any name occurrence
        if name_positions:
            min_dist = min(abs(m.start() - npos) for npos in name_positions)
        else:
            min_dist = m.start()  # use absolute position as proxy
        matches.append((min_dist, is_elem, name, m.start()))

    # Deduplicate: keep the closest occurrence of each unique school name
    seen: dict[str, tuple] = {}
    for dist, is_elem, name, pos in matches:
        if name not in seen or dist < seen[name][0]:
            seen[name] = (dist, is_elem, pos)

    # Sort: non-elementary first, then by distance
    ranked = sorted(seen.items(), key=lambda x: (x[1][1], x[1][0]))

    # Build result with province for each school
    result = []
    for school, (dist, is_elem, pos) in ranked:
        prov = province_after(text, school)
        result.append((school, prov))

    return result


def process_file(filepath: str) -> dict:
    with open(filepath, encoding="utf-8") as f:
        data = json.load(f)

    row_num    = data.get("row", 0)
    full_name  = data.get("full_name", "")
    clean_name = data.get("clean_name", "")

    text    = extract_text_from_json(data)
    schools = ranked_schools(text, clean_name)[:MAX_SCHOOLS]

    result = {
        "row":        row_num,
        "full_name":  full_name,
        "clean_name": clean_name,
    }
    for i, (school, province) in enumerate(schools, start=1):
        result[f"school_{i}"]   = school
        result[f"province_{i}"] = province
    # Fill empty slots so every row has the same columns
    for i in range(len(schools) + 1, MAX_SCHOOLS + 1):
        result[f"school_{i}"]   = ""
        result[f"province_{i}"] = ""

    return result


def main():
    json_files = sorted(glob(os.path.join(INPUT_DIR, "*.json")))
    if not json_files:
        print(f"No JSON files found in '{INPUT_DIR}/'. Run step1_fetch_serper.py first.")
        return

    print(f"Found {len(json_files)} JSON files in '{INPUT_DIR}/'.\n")

    rows = []
    for path in json_files:
        try:
            row = process_file(path)
            rows.append(row)
            # Print preview: name + up to 3 schools
            schools_preview = "  |  ".join(
                f"{row[f'school_{i}'][:28]} ({row[f'province_{i}']})"
                for i in range(1, MAX_SCHOOLS + 1)
                if row.get(f"school_{i}")
            )
            print(f"  [{row['row']:04d}] {row['clean_name']:<25}  {schools_preview}")
        except Exception as e:
            print(f"  ERROR processing {path}: {e}")

    # Sort by original Excel row number
    rows.sort(key=lambda r: r["row"])

    # Build fieldnames: base cols + school_1/province_1 ... school_N/province_N
    fieldnames = ["row", "full_name", "clean_name"]
    for i in range(1, MAX_SCHOOLS + 1):
        fieldnames += [f"school_{i}", f"province_{i}"]

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nDone — {len(rows)} students written to '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()
