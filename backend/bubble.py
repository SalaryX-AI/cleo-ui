"""
Bubble.io API integration for Cleo HR.
Handles all Bubble API calls across job, candidate, passport and interview flows.
Mirrors the structure of xano.py, xano_passport.py and xano_interview.py.
Used when api_source == "bubble".
"""

import requests
from datetime import datetime

# ── Base URL ──────────────────────────────────────────────────────────────────
BUBBLE_BASE_URL = "https://salaryx-98528.bubbleapps.io/version-test/api/1.1"

# ── Endpoints ─────────────────────────────────────────────────────────────────
BUBBLE_GET_JOB_URL              = f"{BUBBLE_BASE_URL}/wf/get_job"
BUBBLE_CREATE_CANDIDATE_URL     = f"{BUBBLE_BASE_URL}/wf/create_candidate"
BUBBLE_PATCH_CANDIDATE_URL      = f"{BUBBLE_BASE_URL}/obj/Candidate_/{{candidate_id}}"
BUBBLE_SEND_EMAIL_URL           = f"{BUBBLE_BASE_URL}/wf/candidate_creation_email"
BUBBLE_CREATE_PASSPORT_URL      = f"{BUBBLE_BASE_URL}/wf/create_passport"
BUBBLE_PATCH_PASSPORT_URL       = f"{BUBBLE_BASE_URL}/obj/Passport_Profiles/{{passport_id}}"
BUBBLE_GET_INTERVIEW_DATA_URL   = f"{BUBBLE_BASE_URL}/wf/interview_data"
BUBBLE_POST_INTERVIEW_URL       = f"{BUBBLE_BASE_URL}/wf/interview_schedule"
BUBBLE_CREATE_USER_URL          = f"{BUBBLE_BASE_URL}/wf/create_user"

BUBBLE_BEARER_TOKEN = "5c30ffa93b0b55a986b8547e07f49e91"


# ── Headers ───────────────────────────────────────────────────────────────────

def _headers() -> dict:
    return {
        "Content-Type":  "application/json",
        "Authorization": f"Bearer {BUBBLE_BEARER_TOKEN}",
    }


# ==================== JOB ====================

def get_job(job_id: str) -> dict:
    """
    Fetch job details from Bubble by job_id.
    Returns normalized dict matching Xano job structure, or {} on failure.
    """
    try:
        resp = requests.get(
            BUBBLE_GET_JOB_URL,
            params  = {"job_id": job_id},
            headers = _headers(),
            timeout = 10,
        )

        if resp.status_code == 200:
            data = resp.json()
            print(f"[BUBBLE] Job fetched: {data.get('Title_', '')} (ID: {job_id})")
            return _normalize_job(data, job_id)

        print(f"[BUBBLE] Job fetch failed: {resp.status_code} — {resp.text}")
        return {}

    except Exception as e:
        print(f"[BUBBLE] Job fetch error: {e}")
        return {}


def _normalize_job(data: dict, job_id: str) -> dict:
    """
    Map Bubble job response fields to internal field names
    matching Xano job structure used in autoInitChatbot.
    """
    shifts      = data.get("shifts", [])
    first_shift = shifts[0] if shifts else {}
    template    = data.get("Job_Template", {})
    company     = data.get("Related_Company", {})
    location    = data.get("Location", {})

    return {
        # Core fields used by main.py / cleoAssistant.js
        "id":                  job_id,
        "job_title":           data.get("Title_", ""),
        "job_template":        data.get("Job_Role", ""),
        "job_location":        location.get("location", ""),
        "related_company":    company.get("company_id", ""),              # no separate company_id in Bubble response
        "job_templates_id":    job_id,              # use job_id as template ref
        "verificationRequired": data.get("Verification_Required_", False),
        "single_company":      False,               # not in Bubble response
        "is_live":             False,
        "Shift":               first_shift.get("Shift", ""),
        "description":         data.get("Job_Description", ""),
        "job_requirements":    data.get("Job_Requirements", ""),

        # Nested
        "_related_company": {
            "company_name":  company.get("name", ""),
            "_related_user": {"single_company": False},
        },
        "_shifts_of_job": [
            {
                "Shift":        first_shift.get("Shift", ""),
                "availability": first_shift.get("availability", []),
            }
        ] if shifts else [],
        "_job_templates": {
            "id":          job_id,
            "role":        data.get("Job_Role", ""),
            "Questions":   template.get("Questions", []),
        },
    }


# ==================== CANDIDATE ====================

def create_candidate(
    name:         str,
    email:        str,
    phone:        str,
    job_id:       str,
    company_id:   str,
    session_id:   str,
    single_company: bool,
) -> str:
    """
    POST to create initial candidate record in Bubble.
    Returns candidate_id (str) or "" on failure.
    """
    status  = "Hiring Manager Review" if single_company else "HR Manager Review"
    payload = {
        "name":                name,
        "email":               email,
        "phone":               phone,
        "job_id":              job_id,
        "company_id":          company_id,
        "status":              status,
        "session_id":          100,
        "my_session_id":       session_id,
        "score":               0,
        "profile_summary":     '{}',
        "conservation_history": '[]',
    }

    try:
        resp = requests.post(
            BUBBLE_CREATE_CANDIDATE_URL,
            json    = payload,
            headers = _headers(),
            timeout = 10,
        )
        if resp.status_code in (200, 204):
            candidate_id = resp.json().get("candidate_id", "")
            print(f"[BUBBLE] Candidate created — ID: {candidate_id}")
            return candidate_id

        print(f"[BUBBLE] Candidate create failed: {resp.status_code} — {resp.text}")
        return ""

    except Exception as e:
        print(f"[BUBBLE] Candidate create error: {e}")
        return ""


def update_candidate(
    candidate_id: str,
    section:      str,
    data:         dict,
) -> bool:
    """
    PATCH candidate record in Bubble.
    Maps internal field names to Bubble field names.
    Returns True on success, False on failure.
    """
    if not candidate_id:
        print(f"[BUBBLE] PATCH skipped — no candidate_id")
        return False

    url     = BUBBLE_PATCH_CANDIDATE_URL.format(candidate_id=candidate_id)
    payload = _map_candidate_fields(data)

    try:
        resp = requests.patch(
            url,
            json    = payload,
            headers = _headers(),
            timeout = 10,
        )
        if resp.status_code in (200, 204):
            print(f"[BUBBLE] Section '{section}' saved — candidate {candidate_id}")
            return True

        print(f"[BUBBLE] PATCH failed ({section}): {resp.status_code} — {resp.text}")
        return False

    except Exception as e:
        print(f"[BUBBLE] PATCH error ({section}): {e}")
        return False


import json as _json

def _map_candidate_fields(data: dict) -> dict:
    """Map internal field names to Bubble Candidate_ field names.
    Bubble expects JSON objects/arrays as strings."""
    field_map = {
        "Name":                  "Name_",
        "Email":                 "Email_",
        "Phone":                 "Phone_",
        "Score":                 "FitScore_",
        "Age":                   "Age_",
        "ProfileSummary":        "Profile_Summary",
        "ConversationHistory":   "Conversation_History",
        "Status":                "Status_",
        "job_id":                "Related_Job_",
        "company_id":            "Company_",
        "session_id":            "Session_id",
        "my_session_id":         "My_session_id",
        "id_verification_result": "ID_Verification_Result",
    }

    # Bubble expects objects/arrays as JSON strings
    STRING_FIELDS = {"Profile_Summary", "Conversation_History"}

    # Fields that are Xano-only (no Bubble equivalent) — drop before sending
    XANO_ONLY_FIELDS = {"email_number"}

    mapped = {}
    for k, v in data.items():
        if k in XANO_ONLY_FIELDS:
            continue
        bubble_key = field_map.get(k, k)
        if bubble_key in STRING_FIELDS and isinstance(v, (dict, list)):
            mapped[bubble_key] = _json.dumps(v)
        else:
            mapped[bubble_key] = v
    return mapped


def send_candidate_email(candidate_id: str) -> bool:
    """
    POST to trigger Bubble welcome email for a candidate.
    Returns True on success, False on failure.
    """
    try:
        resp = requests.post(
            BUBBLE_SEND_EMAIL_URL,
            params  = {"candidate_id": candidate_id},
            headers = _headers(),
            timeout = 10,
        )
        if resp.status_code in (200, 204):
            print(f"[BUBBLE] Welcome email triggered for candidate {candidate_id}")
            return True

        print(f"[BUBBLE] Email trigger failed: {resp.status_code} — {resp.text}")
        return False

    except Exception as e:
        print(f"[BUBBLE] Email trigger error: {e}")
        return False


# ==================== PASSPORT ====================

def create_passport(session_id: str) -> str:
    """
    POST to create initial passport record in Bubble.
    Returns passport_id (str) or "" on failure.
    """
    payload = {
        "name":            "",
        "email":           "",
        "phone":           "",
        "session_id":      "0",
        "my_session_id":   session_id,
        "score":           0,
        "shift_preference": "",
        "location":        "",
        "passport_profile": "",
    }

    try:
        resp = requests.post(
            BUBBLE_CREATE_PASSPORT_URL,
            json    = payload,
            headers = _headers(),
            timeout = 10,
        )
        if resp.status_code in (200, 204):
            response_data = resp.json()
            passport_id   = response_data.get("id", response_data.get("passport_id", ""))

            print(f"[BUBBLE] Passport created — ID: {passport_id}")
            return passport_id

        print(f"[BUBBLE] Passport create failed: {resp.status_code} — {resp.text}")
        return ""

    except Exception as e:
        print(f"[BUBBLE] Passport create error: {e}")
        return ""


def create_user(name: str, email: str) -> str:
    """
    Create a candidate auth account in Bubble for Work Passport onboarding.
    Returns user_id (str) or "" on failure.
    """
    try:
        resp = requests.post(
            BUBBLE_CREATE_USER_URL,
            json    = {"name": name, "email": email},
            headers = _headers(),
            timeout = 10,
        )
        if resp.status_code == 200:
            user_id = resp.json().get("user_id", "")
            print(f"[BUBBLE] User account created — ID: {user_id}")
            return user_id

        print(f"[BUBBLE] User create failed: {resp.status_code} — {resp.text}")
        return ""

    except Exception as e:
        print(f"[BUBBLE] User create error: {e}")
        return ""


def update_passport(
    passport_id: str,
    section:     str,
    data:        dict,
) -> bool:
    """
    PATCH passport record in Bubble.
    Returns True on success, False on failure.
    """
    if not passport_id:
        print(f"[BUBBLE] Passport PATCH skipped — no passport_id")
        return False

    url     = BUBBLE_PATCH_PASSPORT_URL.format(passport_id=passport_id)
    payload = _map_passport_fields(data)

    try:
        resp = requests.patch(
            url,
            json    = payload,
            headers = _headers(),
            timeout = 10,
        )
        if resp.status_code in (200, 204):
            print(f"[BUBBLE] Passport section '{section}' saved — {passport_id}")
            return True

        print(f"[BUBBLE] Passport PATCH failed ({section}): {resp.status_code} — {resp.text}")
        return False

    except Exception as e:
        print(f"[BUBBLE] Passport PATCH error ({section}): {e}")
        return False


def _map_passport_fields(data: dict) -> dict:
    """Map internal passport field names to Bubble Passport_Profiles field names.
    Bubble expects passport_profile/shift_preference as JSON strings; location
    expects a plain human-readable address string, not the raw address object."""
    field_map = {
        "name":             "name",
        "email":            "email",
        "phone":            "phone",
        "score":            "score",
        "shift_preference": "shift_preference",
        "location":         "location",
        "passport_profile": "passport_profile",
        "my_session_id":    "my_session_id",
    }

    # Fields with no confirmed Bubble equivalent yet — drop before sending
    NO_BUBBLE_FIELD = {"status", "passport_link"}

    STRING_FIELDS = {"passport_profile", "shift_preference"}

    mapped = {}
    for k, v in data.items():
        if k in NO_BUBBLE_FIELD:
            continue
        bubble_key = field_map.get(k, k)
        if bubble_key == "location" and isinstance(v, dict):
            mapped[bubble_key] = v.get("full") or v.get("city") or ""
        elif bubble_key in STRING_FIELDS and isinstance(v, (dict, list)):
            mapped[bubble_key] = _json.dumps(v)
        else:
            mapped[bubble_key] = v
    return mapped


# ==================== INTERVIEW ====================

def get_candidate_data(candidate_id: str) -> dict:
    """
    Fetch candidate name/email/phone/address from Bubble for interview scheduling.
    Returns normalized dict matching Xano get_candidate() structure, or {} on failure.
    """
    try:
        resp = requests.get(
            f"{BUBBLE_BASE_URL}/wf/get_candidate_data",
            params  = {"candidate_id": candidate_id},
            headers = _headers(),
            timeout = 10,
        )

        if resp.status_code == 200:
            data = resp.json()
            print(f"[BUBBLE] Candidate data fetched: {data.get('name', '')} (ID: {candidate_id})")
            return {
                "name":    data.get("name", ""),
                "email":   data.get("email", ""),
                "phone":   data.get("phone", ""),
                "address": data.get("address", ""),
            }

        print(f"[BUBBLE] Candidate data fetch failed: {resp.status_code} — {resp.text}")
        return {}

    except Exception as e:
        print(f"[BUBBLE] Candidate data fetch error: {e}")
        return {}


BUBBLE_DEFAULT_AVAILABILITY = [
    {"day": "Sun", "day_as_number": 0, "start_time": "09:00 AM", "end_time": "05:00 PM"},
    {"day": "Mon", "day_as_number": 1, "start_time": "09:00 AM", "end_time": "05:00 PM"},
    {"day": "Tue", "day_as_number": 2, "start_time": "09:00 AM", "end_time": "05:00 PM"},
    {"day": "Wed", "day_as_number": 3, "start_time": "09:00 AM", "end_time": "05:00 PM"},
    {"day": "Thu", "day_as_number": 4, "start_time": "09:00 AM", "end_time": "05:00 PM"},
    {"day": "Fri", "day_as_number": 5, "start_time": "09:00 AM", "end_time": "05:00 PM"},
    {"day": "Sat", "day_as_number": 6, "start_time": "09:00 AM", "end_time": "05:00 PM"},
]


def _parse_bubble_date(date_str: str) -> str:
    """
    Convert Bubble date format "6/12/26" to "2026-06-12".
    Returns original string on failure.
    """
    try:
        dt = datetime.strptime(date_str, "%m/%d/%y")
        return dt.strftime("%Y-%m-%d")
    except Exception:
        try:
            dt = datetime.strptime(date_str, "%Y-%m-%d")
            return date_str
        except Exception:
            print(f"[BUBBLE] Could not parse date: {date_str}")
            return date_str


def get_interview_data(candidate_id: str) -> dict:
    """
    Fetch interview availability data from Bubble.
    Returns normalized dict matching Xano interview_data structure, or {} on failure.
    """
    try:
        resp = requests.get(
            BUBBLE_GET_INTERVIEW_DATA_URL,
            params  = {"candidate_id": candidate_id},
            headers = _headers(),
            timeout = 10,
        )

        if resp.status_code == 200:
            data         = resp.json()
            availability = data.get("Availability", {})
            time_data    = data.get("time", {})
            raw_dates    = availability.get("Interview_dates", [])

            # Parse Bubble date format to YYYY-MM-DD
            parsed_dates = [_parse_bubble_date(d) for d in raw_dates]

            # Use availability from response or fallback to default
            avail_windows = time_data.get("availability", [])
            if not avail_windows:
                print(f"[BUBBLE] Empty availability — using default 9AM-5PM all days")
                avail_windows = BUBBLE_DEFAULT_AVAILABILITY

            print(f"[BUBBLE] Interview data fetched for candidate {candidate_id}")
            return {
                "interview_dates":    parsed_dates,
                "interview_duration": availability.get("interview_duration", 30),
                "google_auth_token":  availability.get(
                                          "_related_user", {}
                                      ).get("Google_authtoken", ""),
                "hiring_manager_id":  availability.get("id", ""),
                "availability":       avail_windows,
            }

        print(f"[BUBBLE] Interview data fetch failed: {resp.status_code} — {resp.text}")
        return {}

    except Exception as e:
        print(f"[BUBBLE] Interview data fetch error: {e}")
        return {}


def post_interview_schedule(
    candidate_id: str,
    date:         str,
    time:         str,
    event_id:     str,
) -> bool:
    """
    POST confirmed interview slot to Bubble.
    Returns True on success, False on failure.
    """
    payload = {
        "candidate_id": candidate_id,
        "date":         date,
        "type":         "",
        "time":         time,
        "meeting_link": "",
        "event_id":     event_id,
    }

    try:
        resp = requests.post(
            BUBBLE_POST_INTERVIEW_URL,
            json    = payload,
            headers = _headers(),
            timeout = 10,
        )
        if resp.status_code == 200:
            print(f"[BUBBLE] Interview scheduled — candidate {candidate_id} @ {date} {time}")
            return True

        print(f"[BUBBLE] Interview schedule failed: {resp.status_code} — {resp.text}")
        return False

    except Exception as e:
        print(f"[BUBBLE] Interview schedule error: {e}")
        return False