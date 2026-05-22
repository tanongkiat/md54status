"""
Step 6 — Convert summary_report.md → summary_report.pdf

Uses fpdf2 with the macOS Ayuthaya TTF font embedded directly.
Converts Markdown headings and tables to a structured PDF.

Reads:  summary_report.md
Writes: summary_report.pdf
"""

import re
import markdown
from fpdf import FPDF
import os

INPUT_MD   = "summary_report.md"
OUTPUT_PDF = "summary_report.pdf"

THAI_FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Ayuthaya.ttf",
    "/System/Library/Fonts/Supplemental/Thonburi.ttc",
]

PAGE_W = 210   # A4 mm
MARGIN = 14
USABLE = PAGE_W - 2 * MARGIN


def find_font():
    for path in THAI_FONT_CANDIDATES:
        if os.path.exists(path):
            return path
    raise FileNotFoundError("No Thai font found. Update THAI_FONT_CANDIDATES.")


class ThaiPDF(FPDF):
    def header(self):
        pass
    def footer(self):
        self.set_y(-10)
        self.set_font("Thai", size=7)
        self.set_text_color(150)
        self.cell(0, 5, f"- {self.page_no()} -", align="C")


def parse_md_table(lines):
    """Parse a markdown table block into (headers, rows)."""
    rows = []
    for line in lines:
        line = line.strip()
        if not line or set(line.replace("|", "").replace("-", "").replace(":", "").replace(" ", "")) == set():
            continue  # separator row
        cells = [c.strip() for c in line.strip("|").split("|")]
        rows.append(cells)
    if len(rows) < 2:
        return None, None
    return rows[0], rows[2:]  # headers, data rows (skip separator)


def draw_table(pdf, headers, rows, col_widths=None):
    """Draw a simple table."""
    n = len(headers)
    if col_widths is None:
        col_widths = [USABLE / n] * n

    # Header row
    pdf.set_fill_color(220, 220, 220)
    pdf.set_font("Thai", style="B", size=8)
    for i, h in enumerate(headers):
        pdf.cell(col_widths[i], 6, h, border=1, fill=True)
    pdf.ln()

    # Data rows
    pdf.set_font("Thai", size=8)
    fill = False
    for row in rows:
        if pdf.get_y() > 270:
            pdf.add_page()
        if fill:
            pdf.set_fill_color(245, 245, 245)
        else:
            pdf.set_fill_color(255, 255, 255)
        for i, cell in enumerate(row):
            w = col_widths[i] if i < len(col_widths) else col_widths[-1]
            pdf.cell(w, 5.5, cell[:60], border=1, fill=True)
        pdf.ln()
        fill = not fill
    pdf.ln(2)


def main():
    if not os.path.exists(INPUT_MD):
        print(f"'{INPUT_MD}' not found. Run step5_summary_report.py first.")
        return

    font_path = find_font()
    print(f"Using font: {font_path}")

    with open(INPUT_MD, encoding="utf-8") as f:
        lines = f.read().splitlines()

    pdf = ThaiPDF(orientation="P", unit="mm", format="A4")
    pdf.add_font("Thai", fname=font_path)
    pdf.add_font("Thai", fname=font_path, style="B")
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_margins(MARGIN, 14, MARGIN)

    i = 0
    while i < len(lines):
        line = lines[i]

        # H1
        if line.startswith("# "):
            pdf.set_font("Thai", style="B", size=16)
            pdf.multi_cell(USABLE, 9, line[2:], ln=True)
            pdf.ln(2)
            i += 1

        # H2
        elif line.startswith("## "):
            if pdf.get_y() > 250:
                pdf.add_page()
            pdf.ln(3)
            pdf.set_font("Thai", style="B", size=11)
            pdf.set_fill_color(230, 235, 245)
            pdf.multi_cell(USABLE, 7, line[3:], border="B", fill=True, ln=True)
            pdf.ln(1)
            i += 1

        # Markdown table
        elif line.startswith("|"):
            table_lines = []
            while i < len(lines) and lines[i].startswith("|"):
                table_lines.append(lines[i])
                i += 1
            headers, rows = parse_md_table(table_lines)
            if headers:
                # Guess col widths: first col wider
                n = len(headers)
                if n == 2:
                    widths = [USABLE * 0.65, USABLE * 0.35]
                elif n == 3:
                    widths = [USABLE * 0.10, USABLE * 0.50, USABLE * 0.40]
                elif n == 4:
                    widths = [USABLE * 0.07, USABLE * 0.35, USABLE * 0.35, USABLE * 0.23]
                else:
                    widths = [USABLE / n] * n
                draw_table(pdf, headers, rows, widths)

        # Blank line
        elif line.strip() == "":
            pdf.ln(1)
            i += 1

        # Normal paragraph text
        else:
            pdf.set_font("Thai", size=9)
            pdf.multi_cell(USABLE, 5.5, line, ln=True)
            i += 1

    pdf.output(OUTPUT_PDF)
    print(f"Saved: {OUTPUT_PDF}  ({pdf.page} pages)")


if __name__ == "__main__":
    main()
