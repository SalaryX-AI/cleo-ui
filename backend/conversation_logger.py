"""
conversation_logger.py
Handles all structured logging for Cleo conversation runs.
Creates two tables:
  - conversation_runs   : one row per session (home screen data)
  - conversation_events : append-only event log (detail view data)
"""

import json
import traceback
from datetime import datetime, timezone
from typing import Optional, Dict, Any

import os
from psycopg import AsyncConnection
from psycopg.rows import dict_row

# ─────────────────────────────────────────────
# DB connection helper
# ─────────────────────────────────────────────

async def _get_conn() -> AsyncConnection:
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING")
    conn = await AsyncConnection.connect(conn_str, autocommit=True, row_factory=dict_row)
    return conn


# ─────────────────────────────────────────────
# Phase 1 – Schema setup (called on app startup)
# ─────────────────────────────────────────────

async def setup_log_tables():
    """Create conversation_runs and conversation_events tables if they don't exist."""
    conn = await _get_conn()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_runs (
                session_id          TEXT PRIMARY KEY,
                thread_id           TEXT NOT NULL,
                job_type            TEXT,
                brand_name          TEXT,
                location            TEXT,
                started_at          TIMESTAMPTZ DEFAULT NOW(),
                last_event_at       TIMESTAMPTZ DEFAULT NOW(),
                status              TEXT DEFAULT 'active',   -- active | completed | errored
                last_node           TEXT,
                last_user_message   TEXT,
                has_error           BOOLEAN DEFAULT FALSE,
                knockout_failed     BOOLEAN DEFAULT FALSE,
                scoring_done        BOOLEAN DEFAULT FALSE,
                error_detail        TEXT
            );
        """)

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS conversation_events (
                id          BIGSERIAL PRIMARY KEY,
                session_id  TEXT NOT NULL,
                thread_id   TEXT NOT NULL,
                node_name   TEXT,
                event_type  TEXT NOT NULL,
                -- event_type values:
                --   node_enter | node_exit | user_message | ai_message
                --   otp_send   | otp_verify | router_decision | interrupt | error
                event_data  JSONB DEFAULT '{}',
                timestamp   TIMESTAMPTZ DEFAULT NOW()
            );
        """)

        # Index for fast lookup by session
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_events_session_id
            ON conversation_events (session_id, timestamp ASC);
        """)

        # Index for full-text search on last_user_message / thread_id
        await conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_runs_thread_id
            ON conversation_runs (thread_id);
        """)

        print("[LOGGER] Log tables ready.")
    finally:
        await conn.close()


# ─────────────────────────────────────────────
# Phase 2 – Logging helpers
# ─────────────────────────────────────────────

async def init_run(
    session_id: str,
    thread_id: str,
    job_type: str,
    brand_name: str,
    location: str,
):
    """Insert a new run row when a session starts."""
    conn = await _get_conn()
    try:
        await conn.execute("""
            INSERT INTO conversation_runs
                (session_id, thread_id, job_type, brand_name, location, status)
            VALUES (%s, %s, %s, %s, %s, 'active')
            ON CONFLICT (session_id) DO NOTHING;
        """, (session_id, thread_id, job_type, brand_name, location))
    except Exception as e:
        print(f"[LOGGER] init_run error: {e}")
    finally:
        await conn.close()


async def log_event(
    session_id: str,
    thread_id: str,
    node_name: Optional[str],
    event_type: str,
    event_data: Optional[Dict[str, Any]] = None,
):
    """
    Append one event row and update last_event_at + last_node on the run row.
    Safe to call fire-and-forget (errors are caught and printed).
    """
    if event_data is None:
        event_data = {}

    conn = await _get_conn()
    try:
        now = datetime.now(timezone.utc)

        await conn.execute("""
            INSERT INTO conversation_events
                (session_id, thread_id, node_name, event_type, event_data, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (session_id, thread_id, node_name, event_type, json.dumps(event_data), now))

        # Keep run row up-to-date
        update_fields = "last_event_at = %s"
        update_vals: list = [now]

        if node_name:
            update_fields += ", last_node = %s"
            update_vals.append(node_name)

        if event_type == "user_message":
            content = event_data.get("content", "")
            update_fields += ", last_user_message = %s"
            update_vals.append(content[:500])   # cap at 500 chars

        if event_type == "error":
            update_fields += ", has_error = TRUE"

        update_vals.append(session_id)
        await conn.execute(
            f"UPDATE conversation_runs SET {update_fields} WHERE session_id = %s;",
            update_vals
        )
    except Exception as e:
        print(f"[LOGGER] log_event error: {e}")
    finally:
        await conn.close()


async def log_router(
    session_id: str,
    thread_id: str,
    router_name: str,
    inputs: Dict[str, Any],
    chosen_branch: str,
):
    """Log a conditional edge / router decision."""
    await log_event(
        session_id=session_id,
        thread_id=thread_id,
        node_name=router_name,
        event_type="router_decision",
        event_data={"inputs": inputs, "chosen_branch": chosen_branch},
    )


async def log_error(
    session_id: str,
    thread_id: str,
    node_name: Optional[str],
    error: Exception,
):
    """Log an exception and mark the run as errored."""
    tb = traceback.format_exc()
    await log_event(
        session_id=session_id,
        thread_id=thread_id,
        node_name=node_name,
        event_type="error",
        event_data={"error": str(error), "traceback": tb},
    )


async def update_run_status(
    session_id: str,
    status: str,              # 'completed' | 'errored'
    error_detail: Optional[str] = None,
    knockout_failed: Optional[bool] = None,
    scoring_done: Optional[bool] = None,
):
    """Update the terminal status of a run."""
    conn = await _get_conn()
    try:
        fields = ["status = %s", "last_event_at = NOW()"]
        vals: list = [status]

        if error_detail is not None:
            fields.append("error_detail = %s")
            vals.append(error_detail[:2000])

        if knockout_failed is not None:
            fields.append("knockout_failed = %s")
            vals.append(knockout_failed)

        if scoring_done is not None:
            fields.append("scoring_done = %s")
            vals.append(scoring_done)

        vals.append(session_id)
        await conn.execute(
            f"UPDATE conversation_runs SET {', '.join(fields)} WHERE session_id = %s;",
            vals
        )
    except Exception as e:
        print(f"[LOGGER] update_run_status error: {e}")
    finally:
        await conn.close()