"""
Step 2.1 — Enrich missing provinces via two passes:

  Pass 1 (fast, free):  keyword-match the school name itself against known
                        province keywords (e.g. โรงเรียนขอนแก่นวิทยายน → ขอนแก่น).

  Pass 2 (Serper API):  only called when a student has NO province found at all
                        after pass 1. Searches Google via Serper using the first
                        available school name (`<school_name> จังหวัด`) and scans
                        titles/snippets for province keywords.

Reads:   student_school_summary.csv
Writes:  student_school_summary.csv  (updated in-place with filled provinces)
         school_province_cache.json  (API result cache, auto-created)

After this step, run the pipeline from step3 onwards.
"""

import csv
import json
import os
import time

import requests

INPUT_FILE   = "student_school_summary.csv"
CACHE_FILE   = "school_province_cache.json"
MAX_SCHOOLS  = 5

SERPER_API_KEY = "bdb17fd93eb5b1c84b97c51a9c8b4a8a42cefc21"
SERPER_URL     = "https://google.serper.dev/search"

# ── All 77 provinces + aliases ─────────────────────────────────────────────────
# Format: (keyword_to_search_in_school_name, canonical_province_name)
# Listed longest/most-specific first within each province to avoid short-alias
# false positives when checking against the full list.
PROVINCE_ALIASES = [
    ("กระบี่",            "กระบี่"),
    ("กาญจนบุรี",         "กาญจนบุรี"),
    ("กาฬสินธุ์",         "กาฬสินธุ์"),
    ("กาฬ",               "กาฬสินธุ์"),
    ("กำแพงเพชร",         "กำแพงเพชร"),
    ("ขอนแก่น",           "ขอนแก่น"),
    ("จันทบุรี",          "จันทบุรี"),
    ("ฉะเชิงเทรา",        "ฉะเชิงเทรา"),
    ("ชลบุรี",            "ชลบุรี"),
    ("ชัยนาท",            "ชัยนาท"),
    ("ชัยภูมิ",           "ชัยภูมิ"),
    ("ชุมพร",             "ชุมพร"),
    ("เชียงราย",          "เชียงราย"),
    ("เชียงใหม่",         "เชียงใหม่"),
    ("ตรัง",              "ตรัง"),
    ("ตราด",              "ตราด"),
    ("ตาก",               "ตาก"),
    ("นครนายก",           "นครนายก"),
    ("นครปฐม",            "นครปฐม"),
    ("นครพนม",            "นครพนม"),
    ("นครราชสีมา",        "นครราชสีมา"),
    ("โคราช",             "นครราชสีมา"),
    ("นครศรีธรรมราช",     "นครศรีธรรมราช"),
    ("นครสวรรค์",         "นครสวรรค์"),
    ("นนทบุรี",           "นนทบุรี"),
    ("นราธิวาส",          "นราธิวาส"),
    ("น่าน",              "น่าน"),
    ("บึงกาฬ",            "บึงกาฬ"),
    ("บุรีรัมย์",         "บุรีรัมย์"),
    ("ปทุมธานี",          "ปทุมธานี"),
    ("ประจวบคีรีขันธ์",   "ประจวบคีรีขันธ์"),
    ("ปราจีนบุรี",        "ปราจีนบุรี"),
    ("ปัตตานี",           "ปัตตานี"),
    ("พระนครศรีอยุธยา",   "พระนครศรีอยุธยา"),
    ("อยุธยา",            "พระนครศรีอยุธยา"),
    ("พะเยา",             "พะเยา"),
    ("พังงา",             "พังงา"),
    ("พัทลุง",            "พัทลุง"),
    ("พิจิตร",            "พิจิตร"),
    ("พิษณุโลก",          "พิษณุโลก"),
    ("เพชรบุรี",          "เพชรบุรี"),
    ("เพชรบูรณ์",         "เพชรบูรณ์"),
    ("แพร่",              "แพร่"),
    ("ภูเก็ต",            "ภูเก็ต"),
    ("มหาสารคาม",         "มหาสารคาม"),
    ("สารคาม",            "มหาสารคาม"),
    ("มุกดาหาร",          "มุกดาหาร"),
    ("แม่ฮ่องสอน",        "แม่ฮ่องสอน"),
    ("ยโสธร",             "ยโสธร"),
    ("ยะลา",              "ยะลา"),
    ("ร้อยเอ็ด",          "ร้อยเอ็ด"),
    ("ระนอง",             "ระนอง"),
    ("ระยอง",             "ระยอง"),
    ("ราชบุรี",           "ราชบุรี"),
    ("ลพบุรี",            "ลพบุรี"),
    ("ลำปาง",             "ลำปาง"),
    ("ลำพูน",             "ลำพูน"),
    ("เลย",               "เลย"),
    ("ศรีสะเกษ",          "ศรีสะเกษ"),
    ("สกลนคร",            "สกลนคร"),
    ("สกล",               "สกลนคร"),
    ("สงขลา",             "สงขลา"),
    ("สตูล",              "สตูล"),
    ("สมุทรปราการ",       "สมุทรปราการ"),
    ("สมุทรสงคราม",       "สมุทรสงคราม"),
    ("สมุทรสาคร",         "สมุทรสาคร"),
    ("สระแก้ว",           "สระแก้ว"),
    ("สระบุรี",           "สระบุรี"),
    ("สิงห์บุรี",         "สิงห์บุรี"),
    ("สุโขทัย",           "สุโขทัย"),
    ("สุพรรณบุรี",        "สุพรรณบุรี"),
    ("สุราษฎร์ธานี",      "สุราษฎร์ธานี"),
    ("สุรินทร์",          "สุรินทร์"),
    ("หนองคาย",           "หนองคาย"),
    ("หนองบัวลำภู",       "หนองบัวลำภู"),
    ("หนองบัว",           "หนองบัวลำภู"),
    ("อ่างทอง",           "อ่างทอง"),
    ("อำนาจเจริญ",        "อำนาจเจริญ"),
    ("อุดรธานี",          "อุดรธานี"),
    ("อุดร",              "อุดรธานี"),
    ("อุตรดิตถ์",         "อุตรดิตถ์"),
    ("อุทัยธานี",         "อุทัยธานี"),
    ("อุบลราชธานี",       "อุบลราชธานี"),
    ("อุบล",              "อุบลราชธานี"),
    ("กรุงเทพมหานคร",     "กรุงเทพมหานคร"),
    ("กรุงเทพ",           "กรุงเทพมหานคร"),
]


def province_from_text(text: str) -> str:
    """Scan arbitrary text for any province keyword; return canonical name."""
    for keyword, canonical in PROVINCE_ALIASES:
        if keyword in text:
            return canonical
    return ""


def serper_search_province(school_name: str) -> str:
    """Query Serper for '<school_name> จังหวัด' and extract province from results."""
    query = f"{school_name} จังหวัด"
    headers = {"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"}
    payload = {"q": query, "gl": "th", "hl": "th", "num": 5}
    try:
        resp = requests.post(SERPER_URL, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        print(f"    [WARN] Serper error for '{school_name}': {e}")
        return ""

    # Collect all text from organic results
    snippets = []
    for item in data.get("organic", []):
        snippets.append(item.get("title", ""))
        snippets.append(item.get("snippet", ""))
        snippets.append(item.get("link", ""))
    combined = " ".join(snippets)
    return province_from_text(combined)


def main():
    if not os.path.exists(INPUT_FILE):
        print(f"'{INPUT_FILE}' not found. Run step2_extract_school.py first.")
        return

    # Load cache
    cache = {}
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, encoding="utf-8") as f:
            cache = json.load(f)

    with open(INPUT_FILE, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        all_rows = list(reader)

    filled_kw = 0   # filled by keyword match
    filled_api = 0  # filled by Serper API
    api_calls  = 0

    enriched_rows = []
    for row in all_rows:
        # Pass 1: keyword-match each school name against province keywords
        for i in range(1, MAX_SCHOOLS + 1):
            school = row.get(f"school_{i}", "").strip()
            prov   = row.get(f"province_{i}", "").strip()
            if school and not prov:
                inferred = province_from_text(school)
                if inferred:
                    row[f"province_{i}"] = inferred
                    filled_kw += 1

        # Pass 2: if still NO province at all for this student, call Serper once
        # using the first available school name as the query
        has_province = any(
            row.get(f"province_{i}", "").strip()
            for i in range(1, MAX_SCHOOLS + 1)
        )
        if not has_province:
            first_school, first_idx = "", -1
            for i in range(1, MAX_SCHOOLS + 1):
                s = row.get(f"school_{i}", "").strip()
                if s:
                    first_school, first_idx = s, i
                    break

            if first_school:
                if first_school not in cache:
                    api_calls += 1
                    print(f"  [{api_calls:04d}] {row.get('clean_name', ''):30s}  → {first_school}")
                    cache[first_school] = serper_search_province(first_school)
                    time.sleep(0.3)

                if cache[first_school]:
                    row[f"province_{first_idx}"] = cache[first_school]
                    filled_api += 1

        enriched_rows.append(row)

    # Save cache
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

    # Save enriched CSV
    with open(INPUT_FILE, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(enriched_rows)

    print(f"\nFilled by keyword match : {filled_kw}")
    print(f"Filled by Serper API    : {filled_api}  ({api_calls} new API calls)")
    print(f"Cache saved to '{CACHE_FILE}'.")
    print(f"Updated '{INPUT_FILE}'.")
    print("\nNow run: python3 step3_filter_non_isan.py")


if __name__ == "__main__":
    main()
