# CTE Explorer (v0.1 — research prototype)

Not a certified compliance tool. Full-text keyword search over official
Spanish CTE PDFs, with every result traceable to a document and page.
No LLM, no embeddings, no compliance checking — this version exists to
establish a search baseline.

## Setup

```bash
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Put official CTE PDFs into `data/` (nothing is included):

```text
data/
    DB-SI.pdf
    DB-SUA.pdf
    DB-HS.pdf
    DB-SE.pdf
    DB-SE-AE.pdf
```

Ingest, then run:

```bash
python -m app.ingest
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000.

Re-running `python -m app.ingest` at any point (new PDFs, replaced PDFs)
is safe — each file's existing rows are replaced before re-inserting.

## How it works

- **Extraction:** PyMuPDF reads each PDF page by page.
- **Section (heading) detection:** heuristic only. The most common font
  size in the document is taken as "body text"; short lines set in a
  noticeably larger font are treated as headings. Each page's `section`
  is the nearest heading at or before it. Where nothing is detected, the
  section is `"Unknown"` — this is shown as such, never guessed silently.
- **Storage:** one row per PDF page in a SQLite FTS5 table
  (`unicode61 remove_diacritics 2` tokenizer, so accented and
  unaccented queries both match).
- **Search:** query terms are tried as an AND match first; if that
  returns nothing, it falls back to OR. Common Spanish function words
  (de, para, el, con, ...) are stripped before searching — without this,
  OR-mode matched pages on nothing but a stray "de" or "para" and
  returned them as if relevant, which was caught while testing (see
  below) and fixed. Ranking is SQLite FTS5's built-in bm25.
- **Page numbers** are always the physical PDF page (1-indexed). This
  prototype has no way to detect a printed page label that differs from
  it, so it never claims one.
- **"Open PDF"** links to `/pdf/<filename>#page=N`, which most browsers'
  built-in PDF viewers honour. Not guaranteed pixel-exact — good enough
  to verify a passage, which is the point.

## What was actually tested, and how

PyMuPDF and FastAPI can't be installed in the sandbox this was built in
(no network access there), so they're untested *in that exact form*.
What was tested, using a clearly-labelled synthetic PDF
(`SYNTHETIC DOCUMENT - NOT CTE`, deleted afterwards — nothing in `data/`
now is real or fake CTE content):

- Heading detection and section-propagation across pages (a page with no
  heading of its own correctly inherited the previous page's section).
- FTS5 schema, accent-insensitive matching, AND-then-OR fallback,
  bm25 ranking.
- **A real bug, found and fixed:** the OR fallback initially returned
  "results" for questions with no actual match in the corpus, because it
  matched on common Spanish function words alone. Fixed by filtering
  stopwords before searching; re-tested and confirmed empty-result
  queries now correctly return nothing.
- Adversarial input (SQL-injection-style punctuation, empty query) — no
  errors, table not affected.
- Empty-corpus and no-match behavior — both return `[]`, which the UI
  renders as "No relevant result found."

The extraction logic was verified using `pdfplumber` as a stand-in for
PyMuPDF (same page/heading/chunking algorithm, different library, since
only `pdfplumber` was available offline). **Run it yourself against a
real CTE PDF before trusting it** — font-size heuristics and real
regulatory documents can interact in ways a 3-page synthetic test won't
surface, especially multi-column layouts or tables.

## Known limitations (by design, not oversights)

- Section detection is a heuristic and will sometimes be wrong or
  `"Unknown"`. It is not a substitute for reading the actual page.
- No table structure extraction — a table's text is included in its
  page's plain text, unparsed.
- No semantic search — a query using different words than the document
  ("sectorización" vs. whatever term the actual PDF uses) may miss
  results that a human would recognise as relevant. This is exactly
  what v0.1 is meant to measure.
- No way to know if a document is the current legally valid version —
  that's on you to verify against codigotecnico.org.

## Project structure

```text
cte-explorer/
├── data/                  # put PDFs here (empty in this delivery)
├── app/
│   ├── database.py        # schema + connection
│   ├── ingest.py          # PDF → SQLite
│   ├── search.py          # FTS5 query logic
│   ├── main.py             # FastAPI app
│   └── templates/index.html
├── requirements.txt
└── README.md
```
