"""
Step 1 — Fetch Serper search results for each student.

Reads:  MDKKU_54.xlsx  (Column C, names start from row 2)
Writes: serper_results/<row>_<clean_name>.json  (one file per student)

Resume-safe: skips students whose JSON file already exists.

Requirements:
    pip install openpyxl requests
"""

import json
import os
import time
import re

import requests
import openpyxl

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_FILE    = "MDKKU_54.xlsx"
OUTPUT_DIR    = "serper_results"
NAME_COLUMN   = 3      # Column C (1-indexed)
HEADER_ROW    = 1      # Row 1 is the header

SERPER_API_KEY = "bdb17fd93eb5b1c84b97c51a9c8b4a8a42cefc21"
SERPER_URL     = "https://google.serper.dev/search"

NUM_RESULTS    = 10    # organic results per query
DELAY_SECONDS  = 0.5  # pause between API calls to avoid rate-limiting
# ──────────────────────────────────────────────────────────────────────────────

HONORIFICS = [
    "นางสาว", "นาง", "นาย", "เด็กหญิง", "เด็กชาย",
    "ดร.", "ศ.", "รศ.", "ผศ.", "พ.ต.", "ร.ต.",
]


def strip_honorific(name: str) -> str:
    for h in HONORIFICS:
        if name.startswith(h):
            return name[len(h):].strip()
    return name


def safe_filename(text: str) -> str:
    """Remove characters that are unsafe in filenames."""
    return re.sub(r'[\\/:*?"<>|]', "_", text)


def read_students(filepath: str, col: int, header_row: int) -> list[dict]:
    """Return list of {row, full_name, clean_name} from the Excel file."""
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    students = []
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        full_name = row[col - 1]
        if full_name and str(full_name).strip():
            full_name  = str(full_name).strip()
            clean_name = strip_honorific(full_name)
            students.append({
                "row":        row_idx,
                "full_name":  full_name,
                "clean_name": clean_name,
            })
    wb.close()
    return students


def serper_search(query: str, num: int = NUM_RESULTS) -> dict:
    """Call Serper.dev and return the full JSON response."""
    response = requests.post(
        SERPER_URL,
        headers={
            "X-API-KEY":    SERPER_API_KEY,
            "Content-Type": "application/json",
        },
        json={"q": query, "gl": "th", "hl": "th", "num": num},
        timeout=15,
    )
    response.raise_for_status()
    return response.json()


def result_path(output_dir: str, row_num: int, clean_name: str) -> str:
    fname = f"{row_num:04d}_{safe_filename(clean_name)}.json"
    return os.path.join(output_dir, fname)


def main():
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    print(f"Reading '{INPUT_FILE}' ...")
    students = read_students(INPUT_FILE, col=NAME_COLUMN, header_row=HEADER_ROW)
    total = len(students)
    print(f"Found {total} students.\n")

    skipped = 0
    fetched = 0
    errors  = 0

    for idx, student in enumerate(students, start=1):
        row_num    = student["row"]
        full_name  = student["full_name"]
        clean_name = student["clean_name"]
        out_path   = result_path(OUTPUT_DIR, row_num, clean_name)

        if os.path.exists(out_path):
            print(f"[{idx}/{total}] SKIP (exists): {full_name}")
            skipped += 1
            continue

        print(f"[{idx}/{total}] Searching: {full_name}")

        queries = {
            "school_background": f'"{clean_name}" โรงเรียน',
            "achievements":      f'"{clean_name}" รางวัล OR เกียรตินิยม OR ทุน OR ชนะเลิศ',
        }

        payload = {
            "row":        row_num,
            "full_name":  full_name,
            "clean_name": clean_name,
            "results":    {},
        }

        success = True
        for key, query in queries.items():
            print(f"    [{key}] {query}")
            try:
                data = serper_search(query)
                payload["results"][key] = data
                time.sleep(DELAY_SECONDS)
            except Exception as e:
                print(f"    ERROR: {e}")
                payload["results"][key] = {"error": str(e)}
                success = False

        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

        if success:
            fetched += 1
            print(f"    Saved → {out_path}")
        else:
            errors += 1
            print(f"    Saved with errors → {out_path}")

    print(f"\nDone. fetched={fetched}  skipped={skipped}  errors={errors}")
    print(f"Results saved in: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
