"""
Xano integration for Cleo Work Passport™
Handles POST (create) and PATCH (update) for the passport table.
Separate from xano.py which handles job application candidates.
"""

import requests

# ── Endpoints ─────────────────────────────────────────────────────────────────
# CTO to confirm final URL once passport table is created in Xano
XANO_PASSPORT_POST_URL  = "https://xoho-w3ng-km3o.n7e.xano.io/api:6skoiMBa/passport_api"
XANO_PASSPORT_PATCH_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:6skoiMBa/passport/{passport_id}"


# ── Headers ───────────────────────────────────────────────────────────────────

def _passport_headers(is_live: bool) -> dict:
    return {
        "Content-Type": "application/json",
        "x-api-key": "sk_test_51QxA9F7C2E8B4D1A6F9C3E7B2A",
        "X-Data-Source": "live" if is_live else "test",
    }


# ── POST — Create passport record ─────────────────────────────────────────────

def create_passport_record(session_id: str, is_live: bool) -> int:
    """
    POST initial passport record at ask_address_node.
    Name/email/phone are empty at this point — PATCHed after phone OTP verified.
    Returns passport_id (int) or 0 on failure.
    """
    payload = {
        "Name":             "",
        "Email":            "",
        "Phone":            "",
        "session_id":       100,
        "my_session_id":    session_id,
        "Status":           "Passport Created",
        "Score":            0,
        "PassportProfile":  {},
        "ShiftPreferences": [],
        "Location":         {},
    }

    try:
        resp = requests.post(
            XANO_PASSPORT_POST_URL,
            json=payload,
            headers=_passport_headers(is_live)
        )
        if resp.status_code == 200:
            passport_id = resp.json().get("id", 0)
            print(f"[PASSPORT] Record created — ID: {passport_id}")
            return passport_id
        print(f"[PASSPORT] POST failed: {resp.status_code} — {resp.text}")
        return 0
    except Exception as e:
        print(f"[PASSPORT] POST error: {e}")
        return 0


# ── PATCH — Update passport section ──────────────────────────────────────────

def update_passport_section(
    passport_id: int,
    section: str,
    data: dict,
    is_live: bool
) -> bool:
    """
    PATCH passport record after each section completes.
    Only sends fields relevant to the completed section.
    PassportProfile is always the full accumulated dict — never partial.
    Returns True on success, False on failure.
    """
    if not passport_id:
        print(f"[PASSPORT] PATCH skipped — no passport_id")
        return False

    url = XANO_PASSPORT_PATCH_URL.format(passport_id=passport_id)
    payload = {"passport_id": passport_id, **data}

    try:
        resp = requests.patch(
            url,
            json=payload,
            headers=_passport_headers(is_live)
        )
        if resp.status_code == 200:
            print(f"[PASSPORT] Section '{section}' saved — passport {passport_id}")
            return True
        print(f"[PASSPORT] PATCH failed ({section}): {resp.status_code} — {resp.text}")
        return False
    except Exception as e:
        print(f"[PASSPORT] PATCH error ({section}): {e}")
        return False


# ── Timeline of Xano writes ───────────────────────────────────────────────────
#
#  ask_address_node
#    └── POST → passport_id stored in state (Name/Email/Phone empty)
#
#  verify_phone_otp_node (phone_verified = True)
#    └── PATCH → Name, Email, Phone
#
#  store_shift_preference_node
#    └── PATCH → ShiftPreferences, PassportProfile (KQs + shift)
#
#  store_address_node
#    └── PATCH → Location, PassportProfile (+ location)
#
#  question_router (all screening Qs done)
#    └── PATCH → PassportProfile (+ screening answers)
#
#  passport_summary_node
#    └── PATCH → Score, Status="Active", PassportProfile (full), passport_link
#
# Each PATCH sends the full accumulated PassportProfile — never partial —
# so Xano always receives the complete object and overwrites cleanly.