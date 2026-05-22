"""
Search school-related information for MD KKU students listed in MDKKU_54.xlsx.
Uses Serper.dev — real Google search results via API (2,500 free searches).

Requirements:
    pip install openpyxl requests
"""

import csv
import os
import time
import requests
import openpyxl

# ── Configuration ─────────────────────────────────────────────────────────────
INPUT_FILE  = "MDKKU_54.xlsx"
OUTPUT_FILE = "student_school_info.csv"
NAME_COLUMN = 3      # Column C (1-indexed)
HEADER_ROW  = 1      # Row 1 is the header

SERPER_API_KEY = "bdb17fd93eb5b1c84b97c51a9c8b4a8a42cefc21"

MAX_RESULTS   = 5    # organic results per query
DELAY_SECONDS = 0.5  # pause between API calls
# ──────────────────────────────────────────────────────────────────────────────

SERPER_URL = "https://google.serper.dev/search"

HONORIFICS = ["นางสาว", "นาง", "นาย", "เด็กหญิง", "เด็กชาย",
              "ดร.", "ศ.", "รศ.", "ผศ.", "พ.ต.", "ร.ต."]


def strip_honorific(name: str) -> str:
    for h in HONORIFICS:
        if name.startswith(h):
            name = name[len(h):].strip()
    return name


def read_student_names(filepath: str, col: int, header_row: int):
    wb = openpyxl.load_workbook(filepath, read_only=True, data_only=True)
    ws = wb.active
    students = []
    for row_idx, row in enumerate(
        ws.iter_rows(min_row=header_row + 1, values_only=True),
        start=header_row + 1,
    ):
        full_name = row[col - 1]
        if full_name and str(full_name).strip():
            full_name = str(full_name).strip()
            clean = strip_honorific(full_name)
            students.append((row_idx, full_name, clean))
    wb.close()
    return students


def serper_search(query: str) -> list[dict]:
    """Call Serper.dev Google Search API and return organic result items."""
    try:
        r = requests.post(
            SERPER_URL,
            headers={"X-API-KEY": SERPER_API_KEY, "Content-Type": "application/json"},
            json={"q": query, "gl": "th", "hl": "th", "num": MAX_RESULTS},
            timeout=15,
        )
        r.raise_for_status()
        return r.json().get("organic", [])
    except Exception as e:
        print(f"    Request failed: {e}")
        return []


def format_results(items: list[dict]) -> str:
    """Flatten results into: Title | URL | Snippet"""
    parts = []
    for item in items:
        title   = item.get("title", "").strip()
        link    = item.get("link", "")
        snippet = item.get("snippet", "").replace("\n", " ").strip()
        parts.append(f"{title} | {link} | {snippet}")
    return " ;; ".join(parts)


def already_done(output_file: str) -> set[int]:
    """Return row numbers already saved so we can resume if interrupted."""
    done = set()
    if os.path.exists(output_file):
        with open(output_file, encoding="utf-8-sig") as f:
            for row in csv.DictReader(f):
                try:
                    done.add(int(row["row"]))
                except (KeyError, ValueError):
                    pass
    return done


def search_student(full_name: str, clean_name: str) -> dict:
    queries = {
        "school_background": f'"{clean_name}" โรงเรียน',
        "achievements":      f'"{clean_name}" รางวัล OR เกียรตินิยม OR ทุน OR ชนะเลิศ',
    }
    result = {"name": full_name, "clean_name": clean_name}
    for key, query in queries.items():
        print(f"    [{key}] {query}")
        items = serper_search(query)
        result[key] = format_results(items)
        time.sleep(DELAY_SECONDS)
    return result


def main():
    print(f"Reading student names from '{INPUT_FILE}' ...")
    students = read_student_names(INPUT_FILE, col=NAME_COLUMN, header_row=HEADER_ROW)
    print(f"Found {len(students)} students.\n")

    done_rows = already_done(OUTPUT_FILE)
    if done_rows:
        print(f"Resuming — {len(done_rows)} students already processed.\n")

    fieldnames = ["row", "name", "clean_name", "school_background", "achievements"]
    file_exists = os.path.exists(OUTPUT_FILE)

    with open(OUTPUT_FILE, "a", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()

        for idx, (row_num, full_name, clean_name) in enumerate(students, start=1):
            if row_num in done_rows:
                print(f"[{idx}/{len(students)}] SKIP: {full_name}")
                continue

            print(f"[{idx}/{len(students)}] {full_name}  ->  {clean_name}")
            data = search_student(full_name, clean_name)
            data["row"] = row_num
            writer.writerow(data)
            csvfile.flush()
            print()

    print(f"Done! Results saved to '{OUTPUT_FILE}'")


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
