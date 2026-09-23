"""Ingest PDFs from data/ into cte.db.

Run: python -m app.ingest

What this does, deliberately kept simple:
  1. For each PDF, extract text page by page.
  2. Guess a rough document "body font size" (the most common span size),
     then treat short lines set in a noticeably larger font as headings.
  3. Each page's `section` = the nearest heading at or before that page.
     This is a heuristic, not real structure parsing. It will be wrong
     sometimes -- when no heading is detected, the section is "Unknown"
     rather than a guess presented as fact.
  4. One row per PAGE goes into the chunks_fts table. page_number is
     always the physical PDF page index (1-indexed) -- never a printed
     page label, which we have no reliable way to detect.

Re-running this script is safe: each document's existing rows are
replaced before re-inserting.
"""

import bisect
import sys
from collections import Counter

import fitz  # PyMuPDF

from app.database import DATA_DIR, ensure_schema, get_connection

HEADING_SIZE_MARGIN = 1.0  # points larger than body text to count as a heading
HEADING_MAX_CHARS = 100    # headings are short lines, not paragraphs


def _document_headings_and_pages(doc: "fitz.Document"):
    """Return (headings, page_texts).

    headings: list of (page_number, heading_text), in page order.
    page_texts: list of page text, index 0 = page 1.
    """
    sizes = []
    for page in doc:
        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:  # not a text block (e.g. image)
                continue
            for line in block["lines"]:
                for span in line["spans"]:
                    if span["text"].strip():
                        sizes.append(round(span["size"], 1))
    body_size = Counter(sizes).most_common(1)[0][0] if sizes else 10.0

    headings = []
    page_texts = []
    for page_index, page in enumerate(doc):
        page_number = page_index + 1
        page_texts.append(page.get_text("text"))

        for block in page.get_text("dict")["blocks"]:
            if block.get("type") != 0:
                continue
            for line in block["lines"]:
                spans = line["spans"]
                if not spans:
                    continue
                line_text = "".join(s["text"] for s in spans).strip()
                if not line_text or len(line_text) > HEADING_MAX_CHARS:
                    continue
                max_size = max(s["size"] for s in spans)
                if max_size >= body_size + HEADING_SIZE_MARGIN and not line_text.endswith("."):
                    headings.append((page_number, line_text))

    return headings, page_texts


def _section_lookup(headings):
    """Return a function page_number -> nearest heading at/before it."""
    heading_pages = [h[0] for h in headings]

    def lookup(page_number: int) -> str:
        idx = bisect.bisect_right(heading_pages, page_number) - 1
        return headings[idx][1] if idx >= 0 else "Unknown"

    return lookup


def ingest_pdf(conn, path) -> int:
    doc = fitz.open(path)
    headings, page_texts = _document_headings_and_pages(doc)
    section_for = _section_lookup(headings)

    filename = path.name
    title = path.stem

    conn.execute("DELETE FROM chunks_fts WHERE filename = ?", (filename,))
    conn.execute("DELETE FROM documents WHERE filename = ?", (filename,))

    cur = conn.execute(
        "INSERT INTO documents (filename, title, path, page_count, ingested_at) "
        "VALUES (?, ?, ?, ?, datetime('now'))",
        (filename, title, str(path), len(doc)),
    )
    document_id = cur.lastrowid

    inserted = 0
    for i, text in enumerate(page_texts):
        page_number = i + 1
        text = text.strip()
        if not text:
            continue
        section = section_for(page_number)
        conn.execute(
            "INSERT INTO chunks_fts (document, section, text, page_number, document_id, filename) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (title, section, text, page_number, document_id, filename),
        )
        inserted += 1

    conn.commit()
    return inserted


def main():
    conn = get_connection()
    ensure_schema(conn)

    pdfs = sorted(DATA_DIR.glob("*.pdf"))
    if not pdfs:
        print(f"No PDFs found in {DATA_DIR}/. Add official CTE PDFs there and re-run.")
        return

    for path in pdfs:
        n_pages = ingest_pdf(conn, path)
        print(f"Ingested {path.name}: {n_pages} pages with text")

    conn.close()


if __name__ == "__main__":
    sys.exit(main())
