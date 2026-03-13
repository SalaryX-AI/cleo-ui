"""
ID Verification Service using Simplici
Supports dev mode (fixed test link) and prod mode (per-applicant unique links).
Switch via environment variable: ID_VERIFY_MODE=dev|prod
"""

import os
import requests
from dotenv import load_dotenv
from psycopg import AsyncConnection

load_dotenv()

ID_VERIFY_MODE = "dev"

# ── Simplici credentials ──────────────────────────────────────────────────────
SIMPLICI_API_KEY        = os.getenv("SIMPLICI_API_KEY", "")
SIMPLICI_APP_ID         = os.getenv("SIMPLICI_APP_ID", "")
SIMPLICI_WEBHOOK_SECRET = os.getenv("SIMPLICI_WEBHOOK_SECRET", "")
SIMPLICI_API_BASE       = "https://api.simplici.io/v1"   

# ── Dev test link (used when ID_VERIFY_MODE=dev) ──────────────────────────────
SIMPLICI_DEV_LINK = "https://secure.beta.simplici.io/697248f9f43e4e9ae660479c?type=qr"


# ── Session creation ──────────────────────────────────────────────────────────

def create_id_verify_session(cleo_session_id: str, applicant_name: str, phone: str) -> tuple[str, str]:
    """
    Create an ID verification session for the applicant.

    DEV  mode: returns the fixed test link + a fake session id. No API call.
    PROD mode: calls Simplici API to generate a unique per-applicant link.

    Returns:
        (verify_link, simplici_session_id)
        On failure returns ("", "")
    """
    if ID_VERIFY_MODE == "dev":
        session_id = "123456"
        print(f"[ID_VERIFY] DEV mode — fixed link, static session id: {session_id}")
        return SIMPLICI_DEV_LINK, session_id

    # ── PROD: call Simplici API ───────────────────────────────────────────────
    try:
        if not SIMPLICI_API_KEY or not SIMPLICI_APP_ID:
            print("[ID_VERIFY] ERROR: SIMPLICI_API_KEY or SIMPLICI_APP_ID not set")
            return "", ""

        response = requests.post(
            f"{SIMPLICI_API_BASE}/sessions",
            headers={
                "Authorization": f"Bearer {SIMPLICI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "appId": SIMPLICI_APP_ID,
                "metadata": {
                    "cleo_session_id": cleo_session_id,
                    "applicant_name":  applicant_name,
                    "phone":           phone
                }
            },
            timeout=10
        )
        response.raise_for_status()
        data = response.json()

        # ⚠️  Adjust field names below once you confirm Simplici's exact response schema
        simplici_session_id = data["sessionId"]
        verify_link         = data["verifyUrl"]

        print(f"[ID_VERIFY] PROD — created session {simplici_session_id} for {applicant_name}")
        return verify_link, simplici_session_id

    except Exception as e:
        print(f"[ID_VERIFY] Error creating Simplici session: {e}")
        return "", ""


# ── PostgreSQL mapping helpers ────────────────────────────────────────────────
# Each function opens its own short-lived connection so it doesn't interfere
# with the AsyncPostgresSaver connection used by LangGraph.

async def _get_conn() -> AsyncConnection:
    """Open a fresh PostgreSQL connection using the same connection string."""
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING")
    return await AsyncConnection.connect(conn_str, autocommit=True)


async def setup_mapping_table() -> None:
    """
    Create the id_verify_sessions table if it doesn't exist.
    Call this once at app startup (from lifespan in main.py).
    """
    conn = await _get_conn()
    try:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS id_verify_sessions (
                simplici_session_id TEXT PRIMARY KEY,
                cleo_session_id     TEXT NOT NULL,
                created_at          TIMESTAMPTZ DEFAULT NOW()
            )
        """)
        print("[ID_VERIFY] id_verify_sessions table ready")
    finally:
        await conn.close()


async def save_session_mapping(simplici_session_id: str, cleo_session_id: str) -> None:
    """
    Persist the simplici_session_id → cleo_session_id mapping to PostgreSQL.
    Called right after create_id_verify_session() in ask_id_verification_node.
    """
    # simplici_session_id = "69b316bc1c27852451484f30"
    
    print(f"[ID_VERIFY] save_session_mapping: "
          f"{simplici_session_id} → {cleo_session_id}")
    
    conn = await _get_conn()
    try:
        await conn.execute("""
            INSERT INTO id_verify_sessions (simplici_session_id, cleo_session_id)
            VALUES (%s, %s)
            ON CONFLICT (simplici_session_id) DO NOTHING
        """, (simplici_session_id, cleo_session_id))
        print(f"[ID_VERIFY] Saved mapping: {simplici_session_id} → {cleo_session_id}")
    finally:
        await conn.close()


async def get_cleo_session_id(simplici_session_id: str) -> str | None:
    """
    Look up the cleo_session_id from a simplici_session_id.
    Called by the webhook endpoint in main.py.
    Returns None if not found.
    """
    conn = await _get_conn()
    try:
        cur = await conn.execute(
            "SELECT cleo_session_id FROM id_verify_sessions WHERE simplici_session_id = %s",
            (simplici_session_id,)
        )
        row = await cur.fetchone()
        return row[0] if row else None
    finally:
        await conn.close()


# ── Webhook signature verification (production safety) ───────────────────────

def verify_webhook_signature(payload_bytes: bytes, received_signature: str) -> bool:
    """
    Verify that the incoming webhook is genuinely from Simplici.
    Uses HMAC-SHA256 with SIMPLICI_WEBHOOK_SECRET.

    Call this inside the webhook endpoint before processing the payload.
    Returns True if valid, False if tampered/invalid.

    ⚠️  Confirm exact header name and signing method with Simplici docs.
    """
    import hmac
    import hashlib

    if not SIMPLICI_WEBHOOK_SECRET:
        print("[ID_VERIFY] WARNING: SIMPLICI_WEBHOOK_SECRET not set — skipping signature check")
        return True   # Allow through in dev; enforce in prod

    expected = hmac.new(
        SIMPLICI_WEBHOOK_SECRET.encode(),
        payload_bytes,
        hashlib.sha256
    ).hexdigest()

    return hmac.compare_digest(expected, received_signature)