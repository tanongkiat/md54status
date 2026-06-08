"""
Compare students between two .doc files and export newly added students to CSV.

Default behavior compares:
- 310700101167_Doctor of Medicine.doc (old)
- 310700101167_Doctor of Medicine_A6904.doc (new)

Usage:
  /opt/homebrew/bin/python3.12 compare_doc_students.py
  /opt/homebrew/bin/python3.12 compare_doc_students.py --old old.doc --new new.doc --out new_students.csv
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import subprocess
import tempfile
from typing import List, Dict


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_OLD_DOC = os.path.join(BASE_DIR, "310700101167_Doctor of Medicine.doc")
DEFAULT_NEW_DOC = os.path.join(BASE_DIR, "310700101167_Doctor of Medicine_A6904.doc")
DEFAULT_OUT_CSV = os.path.join(BASE_DIR, "new_students_A6904.csv")

STUDENT_ID_RE = re.compile(r"^\d{9}-\d$")
THAI_NAME_RE = re.compile(r"^[\u0E00-\u0E7F\.\s]+$")


def doc_to_lines(doc_path: str) -> List[str]:
    """Convert a .doc file to text with textutil and return non-empty lines."""
    if not os.path.exists(doc_path):
        raise FileNotFoundError(f"File not found: {doc_path}")

    with tempfile.NamedTemporaryFile(prefix="students_", suffix=".txt", delete=False) as tmp:
        txt_path = tmp.name

    try:
        subprocess.run(
            ["textutil", "-convert", "txt", doc_path, "-output", txt_path],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        with open(txt_path, "r", encoding="utf-8", errors="ignore") as f:
            return [line.strip() for line in f if line.strip()]
    finally:
        if os.path.exists(txt_path):
            os.remove(txt_path)


def looks_like_name(line: str) -> bool:
    """Heuristic check for Thai full-name lines."""
    if not THAI_NAME_RE.match(line):
        return False

    if line.isdigit():
        return False

    # At least two tokens (first and last name)
    parts = line.split()
    if len(parts) < 2:
        return False

    # Reduce false matches from one-word administrative lines
    return len(line) >= 8


def extract_students(doc_path: str) -> List[Dict[str, str]]:
    """Extract student records as [{'student_id': ..., 'full_name': ...}, ...]."""
    lines = doc_to_lines(doc_path)
    students: List[Dict[str, str]] = []

    i = 0
    while i < len(lines):
        line = lines[i]
        if STUDENT_ID_RE.match(line):
            student_id = line
            full_name = ""

            # Search the next few lines for the matching name.
            for j in range(i + 1, min(i + 6, len(lines))):
                candidate = lines[j]
                if STUDENT_ID_RE.match(candidate):
                    break
                if looks_like_name(candidate):
                    full_name = candidate
                    break

            if full_name:
                students.append({"student_id": student_id, "full_name": full_name})
        i += 1

    return students


def find_new_students(old_doc: str, new_doc: str) -> List[Dict[str, str]]:
    old_students = extract_students(old_doc)
    new_students = extract_students(new_doc)

    old_ids = {s["student_id"] for s in old_students}
    added = [s for s in new_students if s["student_id"] not in old_ids]
    return added


def write_csv(rows: List[Dict[str, str]], output_csv: str) -> None:
    with open(output_csv, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=["student_id", "full_name"])
        writer.writeheader()
        writer.writerows(rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compare two .doc student lists and export newly added students.")
    parser.add_argument("--old", default=DEFAULT_OLD_DOC, help="Path to old .doc file")
    parser.add_argument("--new", default=DEFAULT_NEW_DOC, help="Path to new .doc file")
    parser.add_argument("--out", default=DEFAULT_OUT_CSV, help="Output CSV path")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    added = find_new_students(args.old, args.new)
    write_csv(added, args.out)

    print(f"Old file: {args.old}")
    print(f"New file: {args.new}")
    print(f"New students found: {len(added)}")
    print(f"CSV written: {args.out}")


if __name__ == "__main__":
    main()
