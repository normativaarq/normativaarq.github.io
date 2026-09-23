"""Full-text search over the ingested CTE pages.

Simple ranking: SQLite FTS5's built-in bm25 (via ORDER BY rank).
Query terms are tried as an AND match first (all terms present); if that
returns nothing, falls back to OR (any term present), since natural-
language Spanish questions often have more words than any single passage
will contain verbatim.
"""

import re

from app.database import get_connection

_TOKEN_RE = re.compile(r"[^\w\-áéíóúñÁÉÍÓÚÑüÜ]+", re.UNICODE)

# Markers used instead of raw HTML tags in snippet(), so the frontend can
# safely HTML-escape the excerpt and then swap markers for <mark> --
# extracted PDF text should never be trusted to already be safe HTML.
MARK_OPEN = "\u0001"
MARK_CLOSE = "\u0002"

# Common Spanish function words. Without filtering these, the OR fallback
# (see search()) can match a page on nothing but "de" or "para" and return
# it as a "relevant" result for a question that has no real match --
# tested and confirmed with a synthetic corpus. Deliberately short list:
# it only needs to strip words with no topical content, not do real NLP.
_STOPWORDS = {
    "el", "la", "los", "las", "un", "una", "unos", "unas", "de", "del",
    "al", "a", "en", "y", "o", "u", "que", "qué", "se", "su", "sus",
    "es", "son", "ser", "hay", "no", "sí", "si", "con", "por", "para",
    "como", "cómo", "más", "mas", "pero", "este", "esta", "estos",
    "estas", "ese", "esa", "esos", "esas", "cual", "cuál", "cuales",
    "cuáles", "quien", "quién", "quienes", "quiénes", "donde", "dónde",
    "cuando", "cuándo", "sobre", "entre", "tengo", "tiene", "tener",
    "necesito", "necesita", "aplica", "aplican", "lo", "le", "les",
}


def _terms(query: str):
    query = _TOKEN_RE.sub(" ", query)
    raw = [t for t in query.split() if len(t) > 1]
    content = [t for t in raw if t.lower() not in _STOPWORDS]
    # If the query was nothing but function words ("¿qué es esto?"),
    # there's no real keyword to search on -- treat as no query rather
    # than matching everything via near-universal stopwords.
    return content


def _run(conn, fts_query: str, limit: int):
    try:
        cur = conn.execute(
            """
            SELECT document, filename, section, page_number,
                   snippet(chunks_fts, 2, ?, ?, '…', 40) AS excerpt
            FROM chunks_fts
            WHERE chunks_fts MATCH ?
            ORDER BY rank
            LIMIT ?
            """,
            (MARK_OPEN, MARK_CLOSE, fts_query, limit),
        )
        return cur.fetchall()
    except Exception:
        # Malformed FTS query syntax slipping through, empty corpus, etc.
        # -- fail closed to "no results", never raise past the API layer.
        return []


def search(query: str, limit: int = 10):
    terms = _terms(query)
    if not terms:
        return []

    quoted = [f'"{t}"' for t in terms]
    and_query = " ".join(quoted)
    or_query = " OR ".join(quoted)

    conn = get_connection()
    rows = _run(conn, and_query, limit)
    if not rows:
        rows = _run(conn, or_query, limit)
    conn.close()

    return [
        {
            "document": r["document"],
            "filename": r["filename"],
            "section": r["section"],
            "page_number": r["page_number"],
            "excerpt": r["excerpt"],
        }
        for r in rows
    ]
