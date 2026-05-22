"""
Read student_school_info.csv and extract only:
  - Student name
  - School name (most frequently mentioned)
  - Province (if found)

Output: student_school_summary.csv
"""

import csv
import re
from collections import Counter

INPUT_FILE  = "student_school_info.csv"
OUTPUT_FILE = "student_school_summary.csv"

# Thai provinces list for province extraction
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


def extract_school_names(text: str) -> list[str]:
    """Return all school names found in text (Thai: starts with โรงเรียน)."""
    # Match โรงเรียน + up to 4 Thai words (no spaces between characters in each word)
    raw = re.findall(r'โรงเรียน[\u0E00-\u0E7F]+(?:\s+[\u0E00-\u0E7F]+){0,3}', text)
    cleaned = []
    for m in raw:
        name = m.strip()
        # Stop at tokens that clearly end the school name
        name = re.split(r'\s*(?:สพม|สพป|ม\.|ป\.|จ\.|ขอ|ผ่าน|ได้|ที่|และ|กับ|เพื่อ)', name)[0].strip()
        # Skip if too short or looks like a fragment
        if len(name) > 8:
            cleaned.append(name)
    return cleaned


def extract_province(text: str, school: str = "") -> str:
    """Return the province most likely associated with the student's school."""
    # First try: province appearing immediately after the school name
    if school:
        after_school = text[text.find(school) + len(school):] if school in text else ""
        window = after_school[:60]  # look in the 60 chars right after school name
        for prov in THAI_PROVINCES:
            if prov in window:
                return prov
    # Fallback: count all province mentions and return the most frequent
    counts = Counter()
    for prov in THAI_PROVINCES:
        c = text.count(prov)
        if c:
            counts[prov] = c
    return counts.most_common(1)[0][0] if counts else ""


def school_near_name(text: str, clean_name: str) -> str:
    """Find the school name closest to an occurrence of the student's own name."""
    # Find all school positions
    school_positions = [(m.start(), m.group()) for m in
                        re.finditer(r'โรงเรียน[\u0E00-\u0E7F]+(?:\s[\u0E00-\u0E7F]+){0,3}', text)]
    # Find all name positions
    name_positions = [m.start() for m in re.finditer(re.escape(clean_name), text)]
    if not school_positions or not name_positions:
        return ""
    best_school = ""
    best_dist   = float("inf")
    for npos in name_positions:
        for spos, sname in school_positions:
            dist = abs(npos - spos)
            if dist < best_dist and "อนุบาล" not in sname:
                best_dist   = dist
                best_school = sname
    # Clean up trailing tokens
    best_school = re.split(
        r'\s*(?:สพม|สพป|ม\.|ป\.|จ\.|ขอ|ผ่าน|ได้|ที่|และ|กับ|เพื่อ)', best_school
    )[0].strip()
    return best_school if len(best_school) > 8 else ""


def main():
    results = []

    with open(INPUT_FILE, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            name       = row.get("name", "").strip()
            clean_name = row.get("clean_name", "").strip()
            background = row.get("school_background", "")
            achievements = row.get("achievements", "")

            combined_text = background + " " + achievements

            schools  = extract_school_names(combined_text)
            school   = most_common_school(schools)
            province = extract_province(combined_text, school)

            results.append({
                "name":       name,
                "clean_name": clean_name,
                "school":     school,
                "province":   province,
            })

    with open(OUTPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        fieldnames = ["name", "clean_name", "school", "province"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(results)

    print(f"Done — {len(results)} students written to {OUTPUT_FILE}")

    # Preview first 5
    print(f"\n{'Name':<30} {'School':<40} {'Province'}")
    print("-" * 85)
    for r in results[:5]:
        print(f"{r['clean_name']:<30} {r['school']:<40} {r['province']}")


if __name__ == "__main__":
    main()
