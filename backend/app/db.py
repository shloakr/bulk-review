"""SQLite app/state database.

SQLite is the source of truth for parsed text (blocks + chunks) and review
state; Qdrant holds only vectors + retrieval payloads.
"""

from __future__ import annotations

import json
import sqlite3
import time
from contextlib import contextmanager

from .config import get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    filename    TEXT NOT NULL,
    page_count  INTEGER NOT NULL,
    chunk_count INTEGER NOT NULL,
    ingested_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS blocks (
    block_id    TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    page        INTEGER NOT NULL,
    block_index INTEGER NOT NULL,
    kind        TEXT NOT NULL,            -- text | table
    text        TEXT NOT NULL,
    bbox        TEXT                       -- json [x0,y0,x1,y1] or null
);
CREATE INDEX IF NOT EXISTS idx_blocks_doc_page ON blocks(document_id, page);

CREATE TABLE IF NOT EXISTS chunks (
    chunk_id    TEXT PRIMARY KEY,
    document_id TEXT NOT NULL,
    page        INTEGER NOT NULL,
    chunk_index INTEGER NOT NULL,
    kind        TEXT NOT NULL,
    text        TEXT NOT NULL,
    bboxes      TEXT                       -- json list of bboxes
);
CREATE INDEX IF NOT EXISTS idx_chunks_doc ON chunks(document_id);

CREATE TABLE IF NOT EXISTS reviews (
    review_id  TEXT PRIMARY KEY,
    prompt     TEXT NOT NULL,
    name       TEXT,
    status     TEXT NOT NULL,             -- PLAN|DISCOVER|QUALIFY|EXTRACT|COMPLETE|FAILED
    plan       TEXT,                       -- json planner output
    error      TEXT,
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS candidates (
    review_id   TEXT NOT NULL,
    document_id TEXT NOT NULL,
    score       REAL NOT NULL,
    rank        INTEGER NOT NULL,
    queries     TEXT,                      -- json list of matching queries
    top_chunks  TEXT,                      -- json list of supporting chunk ids
    PRIMARY KEY (review_id, document_id)
);

CREATE TABLE IF NOT EXISTS qualifications (
    review_id   TEXT NOT NULL,
    document_id TEXT NOT NULL,
    is_relevant INTEGER,
    reason      TEXT,
    evidence    TEXT,                      -- json list of chunk ids
    error       TEXT,
    PRIMARY KEY (review_id, document_id)
);

CREATE TABLE IF NOT EXISTS results (
    review_id   TEXT NOT NULL,
    document_id TEXT NOT NULL,
    fields      TEXT,                      -- json {key: {value,status,citation_ids}}
    status      TEXT NOT NULL,             -- pending|running|done|failed
    tool_calls  TEXT,                      -- json list of tool-call summaries
    error       TEXT,
    PRIMARY KEY (review_id, document_id)
);

CREATE TABLE IF NOT EXISTS events (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    review_id TEXT NOT NULL,
    ts        REAL NOT NULL,
    stage     TEXT NOT NULL,
    message   TEXT NOT NULL,
    data      TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_review ON events(review_id, id);
"""


def connect() -> sqlite3.Connection:
    s = get_settings()
    conn = sqlite3.connect(s.sqlite_path, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def init_db():
    with connect() as conn:
        conn.executescript(SCHEMA)


@contextmanager
def db():
    conn = connect()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def add_event(review_id: str, stage: str, message: str, data: dict | None = None):
    with db() as conn:
        conn.execute(
            "INSERT INTO events (review_id, ts, stage, message, data) VALUES (?,?,?,?,?)",
            (review_id, time.time(), stage, message, json.dumps(data) if data else None),
        )


def set_review_status(review_id: str, status: str, error: str | None = None):
    with db() as conn:
        conn.execute(
            "UPDATE reviews SET status=?, error=?, updated_at=? WHERE review_id=?",
            (status, error, time.time(), review_id),
        )
