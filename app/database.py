"""SQLite connection + schema for CTE Explorer.

Everything lives in one file, cte.db, at the project root. There is no
migration system: this is a research prototype, and ensure_schema() is
idempotent (CREATE ... IF NOT EXISTS), so re-running ingest is always safe.
"""

import sqlite3
import pathlib

BASE_DIR = pathlib.Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "cte.db"
DATA_DIR = BASE_DIR / "data"

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    id INTEGER PRIMARY KEY,
    filename TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    path TEXT NOT NULL,
    page_count INTEGER NOT NULL,
    ingested_at TEXT NOT NULL
);

-- One row per PDF page. `document`/`section`/`text` are the searchable
-- columns; the rest are metadata only (UNINDEXED = stored but not
-- tokenized/searched). page_number is the physical PDF page (1-indexed),
-- never a printed page label -- we don't have a reliable way to know if
-- those differ, so we don't pretend to.
CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    document,
    section,
    text,
    page_number UNINDEXED,
    document_id UNINDEXED,
    filename UNINDEXED,
    tokenize = 'unicode61 remove_diacritics 2'
);
"""


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
