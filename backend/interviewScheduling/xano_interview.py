"""
Xano integration for Cleo Interview Scheduling flow.
Handles candidate fetch, interview data fetch, booked slots, and schedule POST.
"""

import requests

# ── Endpoints ─────────────────────────────────────────────────────────────────
XANO_CANDIDATE_URL      = "https://xoho-w3ng-km3o.n7e.xano.io/api:6skoiMBa/candidate/{candidate_id}"
XANO_INTERVIEW_DATA_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:6skoiMBa/interview_data?candidate_id={candidate_id}"
XANO_SCHEDULE_URL       = "https://xoho-w3ng-km3o.n7e.xano.io/api:6skoiMBa/interview/schedule_used"


# ── Headers ───────────────────────────────────────────────────────────────────

def _headers(is_live: bool = False) -> dict:
    return {
        "Content-Type": "application/json",
        "x-api-key":    "sk_test_51QxA9F7C2E8B4D1A6F9C3E7B2A",
        "X-Data-Source": "live",
    }


# ── GET Candidate ─────────────────────────────────────────────────────────────

def get_candidate(candidate_id: str, is_live: bool = False) -> dict:
    """
    Fetch candidate details by ID.
    Returns dict with name, email, phone or {} on failure.
    """
    try:
        url  = XANO_CANDIDATE_URL.format(candidate_id=candidate_id)
        resp = requests.get(url, headers=_headers(is_live), timeout=10)

        if resp.status_code == 200:
            data = resp.json()
            print(f"[INTERVIEW] Candidate fetched: {data.get('Name', '')} (ID: {candidate_id})")
            return {
                "name":       data.get("Name", ""),
                "email":      data.get("Email", ""),
                "phone":      data.get("Phone", ""),
                "job_id":     data.get("job_id", ""),
                "company_id": data.get("company_id", ""),
                "address":    data.get("ProfileSummary", {}).get(
                                  "applicant_information", {}
                              ).get("address", {}),
            }

        print(f"[INTERVIEW] Candidate fetch failed: {resp.status_code} — {resp.text}")
        return {}

    except Exception as e:
        print(f"[INTERVIEW] Candidate fetch error: {e}")
        return {}


# ── GET Interview Data ────────────────────────────────────────────────────────

def get_interview_data(candidate_id: str, is_live: bool = False) -> dict:
    """
    Fetch interview availability, dates, duration, and Google auth token.
    Returns structured dict or {} on failure.
    """
    try:
        url  = XANO_INTERVIEW_DATA_URL.format(candidate_id=candidate_id)
        resp = requests.get(url, headers=_headers(is_live), timeout=10)

        if resp.status_code == 200:
            data         = resp.json()
            availability = data.get("Availability", {})
            time_data    = data.get("time", {})

            print(f"[INTERVIEW] Interview data fetched for candidate {candidate_id}")
            return {
                "interview_dates":    availability.get("Interview_dates", []),
                "interview_duration": availability.get("interview_duration", 30),
                "google_auth_token":  availability.get(
                                          "_related_user", {}
                                      ).get("Google_authtoken", ""),
                "hiring_manager_id":  availability.get("hm", ""),
                "availability":       time_data.get("availability", []),
            }

        print(f"[INTERVIEW] Interview data fetch failed: {resp.status_code} — {resp.text}")
        return {}

    except Exception as e:
        print(f"[INTERVIEW] Interview data fetch error: {e}")
        return {}


# ── POST Schedule ─────────────────────────────────────────────────────────────

def post_schedule(
    candidate_id: str,
    date:         str,
    time:         str,
    event_id:     str,
    is_live:      bool = False
) -> bool:
    """
    POST confirmed interview slot to Xano.
    Returns True on success, False on failure.
    """
    payload = {
        "candidate_id": int(candidate_id) if str(candidate_id).isdigit() else candidate_id,
        "date":         date,
        "type":         "",
        "time":         time,
        "meeting_link": "",
        "event_id":     event_id,
    }

    try:
        resp = requests.post(
            XANO_SCHEDULE_URL,
            json=payload,
            headers=_headers(is_live),
            timeout=10
        )
        if resp.status_code == 200:
            print(f"[INTERVIEW] Schedule posted — candidate {candidate_id} @ {date} {time}")
            return True

        print(f"[INTERVIEW] Schedule post failed: {resp.status_code} — {resp.text}")
        return False

    except Exception as e:
        print(f"[INTERVIEW] Schedule post error: {e}")
        return False
