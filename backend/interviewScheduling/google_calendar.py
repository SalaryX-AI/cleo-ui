"""
Google Calendar integration for Cleo Interview Scheduling.
Creates interview events and fetches busy slots from manager's calendar.
"""

import requests
import pytz
from datetime import datetime, timedelta

GOOGLE_FREEBUSY_URL = "https://www.googleapis.com/calendar/v3/freeBusy"


# ── US State → Timezone map ───────────────────────────────────────────────────

US_STATE_TIMEZONES = {
    "AL": "America/Chicago",
    "AK": "America/Anchorage",
    "AZ": "America/Phoenix",
    "AR": "America/Chicago",
    "CA": "America/Los_Angeles",
    "CO": "America/Denver",
    "CT": "America/New_York",
    "DE": "America/New_York",
    "FL": "America/New_York",
    "GA": "America/New_York",
    "HI": "Pacific/Honolulu",
    "ID": "America/Denver",
    "IL": "America/Chicago",
    "IN": "America/Indiana/Indianapolis",
    "IA": "America/Chicago",
    "KS": "America/Chicago",
    "KY": "America/New_York",
    "LA": "America/Chicago",
    "ME": "America/New_York",
    "MD": "America/New_York",
    "MA": "America/New_York",
    "MI": "America/Detroit",
    "MN": "America/Chicago",
    "MS": "America/Chicago",
    "MO": "America/Chicago",
    "MT": "America/Denver",
    "NE": "America/Chicago",
    "NV": "America/Los_Angeles",
    "NH": "America/New_York",
    "NJ": "America/New_York",
    "NM": "America/Denver",
    "NY": "America/New_York",
    "NC": "America/New_York",
    "ND": "America/Chicago",
    "OH": "America/New_York",
    "OK": "America/Chicago",
    "OR": "America/Los_Angeles",
    "PA": "America/New_York",
    "RI": "America/New_York",
    "SC": "America/New_York",
    "SD": "America/Chicago",
    "TN": "America/Chicago",
    "TX": "America/Chicago",
    "UT": "America/Denver",
    "VT": "America/New_York",
    "VA": "America/New_York",
    "WA": "America/Los_Angeles",
    "WV": "America/New_York",
    "WI": "America/Chicago",
    "WY": "America/Denver",
    "DC": "America/New_York",
}

DEFAULT_TIMEZONE = "America/New_York"

GOOGLE_CALENDAR_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"


def get_timezone_from_state(state_code: str) -> str:
    """Return timezone string for a US state code. Defaults to America/New_York."""
    return US_STATE_TIMEZONES.get(state_code.upper().strip(), DEFAULT_TIMEZONE)


def get_busy_slots_for_date(
    auth_token: str,
    date_str:   str,
    timezone:   str,
    start_time: str = "09:00 AM",
    end_time:   str = "05:00 PM",
) -> list:
    """
    Fetch busy time periods from manager's Google Calendar for a specific date.
    Uses FreeBusy API.

    Args:
        auth_token: Manager's Google OAuth token
        date_str:   "2026-08-16"
        timezone:   "America/New_York"
        start_time: Availability window start e.g. "09:00 AM"
        end_time:   Availability window end   e.g. "05:00 PM"

    Returns:
        List of busy periods as dicts: [{"start": datetime, "end": datetime}]
        Times are in the local timezone for comparison with generated slots.
        Returns [] on failure (no filtering applied).
    """
    try:
        tz     = pytz.timezone(timezone)

        # Build timeMin and timeMax in UTC
        day_start = datetime.strptime(f"{date_str} {start_time}", "%Y-%m-%d %I:%M %p")
        day_end   = datetime.strptime(f"{date_str} {end_time}",   "%Y-%m-%d %I:%M %p")

        # Localize to the job timezone then convert to UTC
        day_start_local = tz.localize(day_start)
        day_end_local   = tz.localize(day_end)
        time_min_utc    = day_start_local.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        time_max_utc    = day_end_local.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        payload = {
            "timeMin": time_min_utc,
            "timeMax": time_max_utc,
            "items":   [{"id": "primary"}],
        }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type":  "application/json",
        }

        resp = requests.post(
            GOOGLE_FREEBUSY_URL,
            json    = payload,
            headers = headers,
            timeout = 10,
        )

        if resp.status_code == 401:
            print(f"[FREEBUSY] Auth token expired or invalid — skipping busy filter")
            return []
        if resp.status_code != 200:
            print(f"[FREEBUSY] Request failed: {resp.status_code} — {resp.text}")
            return []

        data        = resp.json()
        busy_raw    = data.get("calendars", {}).get("primary", {}).get("busy", [])

        # Convert UTC busy periods back to local timezone for slot comparison
        busy_local = []
        for period in busy_raw:
            start_utc = datetime.strptime(period["start"], "%Y-%m-%dT%H:%M:%SZ")
            end_utc   = datetime.strptime(period["end"],   "%Y-%m-%dT%H:%M:%SZ")
            start_loc = pytz.utc.localize(start_utc).astimezone(tz).replace(tzinfo=None)
            end_loc   = pytz.utc.localize(end_utc).astimezone(tz).replace(tzinfo=None)
            busy_local.append({"start": start_loc, "end": end_loc})

        print(f"[FREEBUSY] {len(busy_local)} busy period(s) on {date_str}")
        for p in busy_local:
            print(f"[FREEBUSY]   Busy: {p['start']} → {p['end']}")
        return busy_local

    except Exception as e:
        print(f"[FREEBUSY] Error: {e}")
        return []


def is_slot_busy(slot_dt: datetime, duration: int, busy_periods: list) -> bool:
    """
    Check if a slot overlaps with any busy period.

    Args:
        slot_dt:      Slot start as naive datetime
        duration:     Slot duration in minutes
        busy_periods: List of {"start": datetime, "end": datetime}

    Returns:
        True if slot overlaps with any busy period.
    """
    slot_end = slot_dt + timedelta(minutes=duration)
    for period in busy_periods:
        # Overlap if slot starts before busy ends AND slot ends after busy starts
        if slot_dt < period["end"] and slot_end > period["start"]:
            return True
    return False


def parse_slot_to_datetime(date_str: str, slot: str) -> tuple[str, str]:
    """
    Convert date + slot to Google Calendar dateTime format.

    Args:
        date_str: "2026-08-14"
        slot:     "10:00 AM" (single time), or a range as generated by
                  generate_slots(): "9:00-9:30 AM" (same period — start has
                  no AM/PM of its own) or "11:45 AM-12:15 PM" (crosses
                  noon — start already carries its own AM/PM).

    Returns:
        (start_datetime, end_datetime) in ISO 8601 format
        e.g. ("2026-08-14T10:00:00", "2026-08-14T10:30:00")
    """
    try:
        start_str = slot
        if "-" in slot:
            start_part, end_part = slot.split("-", 1)
            start_part = start_part.strip()
            end_part   = end_part.strip()
            if not any(p in start_part.upper() for p in ("AM", "PM")):
                # Start has no period marker of its own — borrow it from the end
                period     = end_part.split()[-1]
                start_part = f"{start_part} {period}"
            start_str = start_part

        dt_start = datetime.strptime(f"{date_str} {start_str}", "%Y-%m-%d %I:%M %p")
        return dt_start.strftime("%Y-%m-%dT%H:%M:%S"), dt_start.strftime("%Y-%m-%dT%H:%M:%S")
    except Exception as e:
        print(f"[CALENDAR] Datetime parse error: {e}")
        return f"{date_str}T09:00:00", f"{date_str}T09:30:00"

def create_interview_event(
    auth_token:       str,
    candidate_name:   str,
    candidate_email:  str,
    date:             str,
    slot:             str,
    duration:         int,
    timezone:         str,
    hiring_manager:   str = "",
) -> str:
    """
    Create interview event on hiring manager's Google Calendar.

    Returns event_id (str) or "" on failure.
    """
    try:
        # Parse start and end times
        start_dt_str, _ = parse_slot_to_datetime(date, slot)
        start_dt         = datetime.strptime(start_dt_str, "%Y-%m-%dT%H:%M:%S")
        end_dt           = start_dt + timedelta(minutes=duration)
        end_dt_str       = end_dt.strftime("%Y-%m-%dT%H:%M:%S")

        payload = {
            "summary":     f"Interview Scheduled with {candidate_name}",
            "description": (
                f"Interview scheduled with {candidate_name}.\n"
                f"Schedule a meeting via this email {candidate_email} if you want online."
            ),
            "start": {
                "dateTime": start_dt_str,
                "timeZone": timezone,
            },
            "end": {
                "dateTime": end_dt_str,
                "timeZone": timezone,
            },
            "colorId": "8",
        }

        headers = {
            "Authorization": f"Bearer {auth_token}",
            "Content-Type":  "application/json",
        }

        resp = requests.post(
            GOOGLE_CALENDAR_URL,
            json=payload,
            headers=headers,
            timeout=10
        )

        if resp.status_code in (200, 201):
            event_id = resp.json().get("id", "")
            print(f"[CALENDAR] Event created — ID: {event_id} for {candidate_name} @ {date} {slot}")
            return event_id

        print(f"[CALENDAR] Event creation failed: {resp.status_code} — {resp.text}")
        return ""

    except Exception as e:
        print(f"[CALENDAR] Event creation error: {e}")
        return ""
