"""
LPD&M Cleaning Solutions — Quote Intake API
============================================
Run:   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
Docs:  http://localhost:8000/docs
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sqlite3
import contextlib
from datetime import datetime, timezone


# ──────────────────────────────────────────────────────────────────────────────
# Application setup
# ──────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="LPD&M Quote API",
    description="Intake and workflow tracking for LPD&M Cleaning Solutions",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],          # Tighten to your domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

DB_FILE = "lpdm_database.db"


# ──────────────────────────────────────────────────────────────────────────────
# Database helpers
# ──────────────────────────────────────────────────────────────────────────────

@contextlib.contextmanager
def get_db():
    """
    Context manager that opens a connection, yields a cursor, commits on
    success, and always closes the connection — even if an exception fires.
    BUG-06 FIX: eliminates the raw open/close pattern that leaks connections
    on errors.
    """
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row          # Rows behave like dicts
    conn.execute("PRAGMA journal_mode=WAL") # Better concurrency on SQLite
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db() -> None:
    """
    Create the quotes table if it does not exist, then safely add any
    columns that are missing from an older schema.

    BUG-02 FIX: preferred_date, referral_source, status added to schema.
    BUG-05 FIX: ALTER TABLE … ADD COLUMN inside try/except guards against
    'duplicate column' errors on databases that already have some columns.
    """
    create_sql = """
        CREATE TABLE IF NOT EXISTS quotes (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            name            TEXT    NOT NULL,
            email           TEXT    NOT NULL,
            phone           TEXT    NOT NULL,
            service         TEXT    NOT NULL,
            property_size   TEXT,
            message         TEXT,
            submitted_at    TEXT    NOT NULL,
            preferred_date  TEXT,
            referral_source TEXT,
            status          TEXT    NOT NULL DEFAULT 'New'
        )
    """

    # Columns that may be absent on databases created before this version
    migration_columns = [
        ("preferred_date",  "TEXT"),
        ("referral_source", "TEXT"),
        ("status",          "TEXT NOT NULL DEFAULT 'New'"),
    ]

    with get_db() as conn:
        conn.execute(create_sql)

        # BUG-05: safe migration — ignore error if column already exists
        for col_name, col_def in migration_columns:
            try:
                conn.execute(
                    f"ALTER TABLE quotes ADD COLUMN {col_name} {col_def}"
                )
            except sqlite3.OperationalError:
                # Column already present — nothing to do
                pass


# Run once at startup
init_db()


# ──────────────────────────────────────────────────────────────────────────────
# Pydantic models
# ──────────────────────────────────────────────────────────────────────────────

class QuoteRequest(BaseModel):
    """
    Fields sent by the public quote form.

    BUG-03 FIX: preferred_date and referral_source added.
    NOTE:  'source' and 'submitted_at' are sent by the JS frontend but
           intentionally ignored here — the server always owns submitted_at.
    """
    name:             str
    email:            str
    phone:            str
    service:          str
    property_size:    Optional[str] = None
    message:          Optional[str] = None
    preferred_date:   Optional[str] = None
    referral_source:  Optional[str] = None

    # Accepted but discarded — frontend sends these, we don't store them as-is
    source:           Optional[str] = None   # always "website" from JS
    submitted_at:     Optional[str] = None   # server will generate its own


class StatusUpdate(BaseModel):
    """Body for the status-update endpoint (reserved for future flexibility)."""
    status: str = "Responded"


# ──────────────────────────────────────────────────────────────────────────────
# Routes
# ──────────────────────────────────────────────────────────────────────────────

@app.post("/v1/quote", status_code=201)
async def receive_quote(request: QuoteRequest):
    """
    Accept a quote request from the public website form and persist it.

    BUG-01 FIX: column list (10) now matches placeholder count (10) exactly.
    BUG-02 FIX: preferred_date, referral_source, status written to DB.
    BUG-06 FIX: uses get_db() context manager — no connection leaks.
    """
    # Server always generates the authoritative timestamp (UTC ISO-8601)
    submitted_at = datetime.now(timezone.utc).isoformat()

    insert_sql = """
        INSERT INTO quotes (
            name,
            email,
            phone,
            service,
            property_size,
            message,
            submitted_at,
            preferred_date,
            referral_source,
            status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    # ── 10 columns above ── 10 values below ──────────────────────────────────
    values = (
        request.name,                   # name
        request.email,                  # email
        request.phone,                  # phone
        request.service,                # service
        request.property_size,          # property_size
        request.message,                # message
        submitted_at,                   # submitted_at  ← server-generated
        request.preferred_date,         # preferred_date
        request.referral_source,        # referral_source
        "New",                          # status        ← always starts as New
    )

    try:
        with get_db() as conn:
            cursor = conn.execute(insert_sql, values)
            new_id = cursor.lastrowid

        return {"status": "success", "id": new_id}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/admin/quotes")
async def get_all_quotes():
    """
    Return all quote submissions, newest first.
    BUG-06 FIX: uses get_db() context manager.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM quotes ORDER BY id DESC"
            )
            rows = cursor.fetchall()

        return [dict(row) for row in rows]

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/admin/quotes/{quote_id}/respond", status_code=200)
async def mark_as_responded(quote_id: int):
    """
    Mark a quote as 'Responded'.

    BUG-04 FIX: this endpoint was completely missing from the original code.
    Dashboard JS calls:  POST /v1/admin/quotes/{id}/respond
    This route matches that path exactly (critical rule: don't change URLs).
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "UPDATE quotes SET status = 'Responded' WHERE id = ?",
                (quote_id,),
            )
            if cursor.rowcount == 0:
                raise HTTPException(
                    status_code=404,
                    detail=f"Quote #{quote_id} not found."
                )

        return {"status": "success", "id": quote_id, "new_status": "Responded"}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/admin/quotes/{quote_id}", status_code=200)
async def get_single_quote(quote_id: int):
    """
    Fetch one quote by ID — used by the dashboard detail modal.
    """
    try:
        with get_db() as conn:
            cursor = conn.execute(
                "SELECT * FROM quotes WHERE id = ?",
                (quote_id,),
            )
            row = cursor.fetchone()

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Quote #{quote_id} not found."
            )

        return dict(row)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ──────────────────────────────────────────────────────────────────────────────
# Health check (useful for monitoring / uptime checks)
# ──────────────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).isoformat()}