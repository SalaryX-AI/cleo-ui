"""
Xano integration for Cleo Work Passport™
Handles POST (create) and PATCH (update) for the passport table.
Separate from xano.py which handles job application candidates.
"""

import requests

# ── Endpoints ─────────────────────────────────────────────────────────────────
# CTO to confirm final URL once passport table is created in Xano
XANO_PASSPORT_POST_URL  = "https://xoho-w3ng-km3o.n7e.xano.io/api:J0eY2LVM/passport_profiles"
XANO_PASSPORT_PATCH_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:J0eY2LVM/passport_profiles/{passport_profiles_id}"
XANO_AUTH_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:LNn6-rP8/auth/signupcandidate"


# ── Headers ───────────────────────────────────────────────────────────────────

def _passport_headers(is_live: bool) -> dict:
    return {
        "Content-Type": "application/json",
        "X-Data-Source": "live",
    }

    
# ── POST — Create passport record ─────────────────────────────────────────────

def create_passport_record(session_id: str, is_live: bool) -> str:
    """
    POST initial passport record at ask_address_node.
    Name/email/phone are empty at this point — PATCHed after phone OTP verified.
    Returns passport_id (str) or "" on failure.
    """

    payload = {
        "name":            "",
        "email":           "",
        "phone":           "",
        "session_id":      100,
        "my_session_id":   session_id,
        "score":           0,
        "passport_profile": {},
        "shift_prefrence": [],
        "location":        {},
    }

    try:
        resp = requests.post(
            XANO_PASSPORT_POST_URL,
            json=payload,
            headers=_passport_headers(is_live)
        )
        print(f"[PASSPORT] POST response: {resp.status_code} — {resp.text}")
        if resp.status_code == 200:
            response_data = resp.json()
            print(f"[PASSPORT] POST response data: {response_data}")
            passport_id = response_data.get("id", response_data.get("_id", 0))
            print(f"[PASSPORT] Record created — ID: {passport_id}")
            return passport_id
        
        print(f"[PASSPORT] POST failed: {resp.status_code} — {resp.text}")
        return ""
    except Exception as e:
        print(f"[PASSPORT] POST error: {e}")
        return ""


# ── PATCH — Update passport section ──────────────────────────────────────────

def update_passport_section(
    passport_id: str,
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

    print(f"[PASSPORT] PATCH '{section}' for passport_id {passport_id} — data: {data}")
    if not passport_id:
        print(f"[PASSPORT] PATCH skipped — no passport_id")
        return False

    url = XANO_PASSPORT_PATCH_URL.format(passport_profiles_id=passport_id)
    payload = {"passport_profiles_id": passport_id, **data}

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


# ── Auth — Create candidate account ──────────────────────────────────────────

def create_candidate_account(name: str, email: str, is_live: bool) -> dict:
    """
    POST to create candidate auth account after passport is complete.
    Returns response dict with authToken etc, or {} on failure.
    """
    payload = {
        "full_name": name,
        "email":     email,
    }

    try:
        resp = requests.post(
            XANO_AUTH_URL,
            json=payload,
            headers=_passport_headers(is_live)
        )
        if resp.status_code == 200:
            data = resp.json()
            print(f"[PASSPORT] Candidate account created for {email} — response: {data}")
            return data
       
        print(f"[PASSPORT] Auth signup failed: {resp.status_code} — {resp.text}")
        return {}
    except Exception as e:
        print(f"[PASSPORT] Auth signup error: {e}")
        return {}


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