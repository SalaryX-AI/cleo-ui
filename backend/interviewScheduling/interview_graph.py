"""
Interview Graph — Cleo Interview Scheduling
Separate LangGraph for conversational interview slot booking.
"""

import re
import time
from datetime import datetime, timedelta
from typing import Literal, List, Dict
from unittest import result

from langgraph.graph import StateGraph, END, MessagesState
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage

from dotenv import load_dotenv

from interviewScheduling.interview_prompts import (
    INTERVIEW_GREETING_PROMPT,
    INTERVIEW_ASK_DATE,
    INTERVIEW_DATE_REASK_PROMPT,
    INTERVIEW_DATE_OFFTOPIC,
    INTERVIEW_NO_SLOTS,
    INTERVIEW_ASK_SLOT,
    INTERVIEW_SLOT_REASK_PROMPT,
    INTERVIEW_SLOT_OFFTOPIC,
    INTERVIEW_CONFIRM_PROMPT,
    INTERVIEW_CONFIRM_REASK,
    INTERVIEW_CONFIRM_OFFTOPIC,
    INTERVIEW_RESELECT,
    INTERVIEW_SUCCESS_PROMPT,
    INTERVIEW_MAX_ATTEMPTS,
    INTERVIEW_CALENDAR_ERROR,
    INTERVIEW_NO_DATES,
    PARSE_DATE_PROMPT,
    PARSE_SLOT_PROMPT,
    PARSE_CONFIRMATION_PROMPT,
    INTERVIEW_EMAIL_SUBJECT,
    INTERVIEW_EMAIL_BODY,
)

from interviewScheduling.xano_interview import (
    get_candidate,
    get_interview_data,
    post_schedule,
)

from interviewScheduling.google_calendar import (
    create_interview_event,
    get_timezone_from_state,
    get_busy_slots_for_date,
    is_slot_busy,
)

from otp_verification import send_email_otp as _brevo_send

load_dotenv()

import bubble as bubble_api

# ── LLM ──────────────────────────────────────────────────────────────────────
llm            = ChatOpenAI(model="gpt-4o-mini", temperature=0.4)
evaluation_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)


# ==================== STATE ====================

class InterviewState(MessagesState):

    # ── Session ───────────────────────────────────────────────────────────────
    session_id:   str  = ""
    is_live:      bool = False

    # ── Candidate ─────────────────────────────────────────────────────────────
    candidate_id:    str = ""
    candidate_name:  str = ""
    candidate_email: str = ""
    candidate_phone: str = ""
    candidate_state: str = ""   # US state code for timezone

    # ── Interview data ────────────────────────────────────────────────────────
    interview_dates:    List[str]  = []
    interview_duration: int        = 30
    availability:       List[Dict] = []
    google_auth_token:  str        = ""
    hiring_manager_id:  str        = ""
    hiring_manager:     str        = ""
    timezone:           str        = "America/New_York"
    booked_slots:       List[str]  = []   # not used — FreeBusy fetched per date

    # ── Selection ─────────────────────────────────────────────────────────────
    selected_date:   str       = ""
    available_slots: List[str] = []
    selected_slot:   str       = ""
    confirmed:       bool      = False
    reselecting_slot:   bool = False

    # ── Result ────────────────────────────────────────────────────────────────
    event_id:   str  = ""
    email_sent: bool = False
    completed:  bool = False

    # ── Re-ask tracking ───────────────────────────────────────────────────────
    re_ask_attempts: Dict[str, int] = {}

    api_source: str = "xano"


# ==================== HELPERS ====================

def format_dates_list(dates: list) -> str:
    """Format dates list for display in chat."""
    lines = []
    for i, d in enumerate(dates, 1):
        try:
            dt      = datetime.strptime(d, "%Y-%m-%d")
            display = dt.strftime("%A, %B %d, %Y")
            lines.append(f"{i}. {display}")
        except Exception:
            lines.append(f"{i}. {d}")
    return "\n".join(lines)


def format_slots_list(slots: list, duration: int = 30) -> str:
    """Format slots list — slots already stored as ranges."""
    return "\n".join([f"{i}. {s}" for i, s in enumerate(slots, 1)])


def format_date_display(date_str: str) -> str:
    """Format YYYY-MM-DD to readable string."""
    try:
        return datetime.strptime(date_str, "%Y-%m-%d").strftime("%A, %B %d, %Y")
    except Exception:
        return date_str


def generate_slots(
    date_str:     str,
    availability:  list,
    duration:     int,
    auth_token:   str,
    timezone:     str,
) -> list:
    """
    Generate available time slots for a date.
    Filters out busy periods from Google Calendar FreeBusy API.
    """
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")

        # Python weekday: Mon=0 ... Sun=6
        # day_as_number:  Sun=0, Mon=1 ... Sat=6
        python_to_avail = {0: 1, 1: 2, 2: 3, 3: 4, 4: 5, 5: 6, 6: 0}
        day_number = python_to_avail[dt.weekday()]

        # Find matching availability window
        window = None
        for avail in availability:
            if avail.get("day_as_number") == day_number:
                window = avail
                break

        if not window:
            print(f"[SLOTS] No availability window for day_number={day_number} on {date_str}")
            return []

        start_time_str = window["start_time"]
        end_time_str   = window["end_time"]

        start = datetime.strptime(f"{date_str} {start_time_str}", "%Y-%m-%d %I:%M %p")
        end   = datetime.strptime(f"{date_str} {end_time_str}",   "%Y-%m-%d %I:%M %p")

        # ── Fetch busy periods from Google Calendar FreeBusy ─────────────────
        busy_periods = get_busy_slots_for_date(
            auth_token = auth_token,
            date_str   = date_str,
            timezone   = timezone,
            start_time = start_time_str,
            end_time   = end_time_str,
        )

        # ── Generate all slots first ──────────────────────────────────────────
        all_slots = []
        cursor    = start
        while cursor + timedelta(minutes=duration) <= end:
            end_cursor    = cursor + timedelta(minutes=duration)
            start_str     = cursor.strftime("%I:%M %p").lstrip("0")
            end_str       = end_cursor.strftime("%I:%M %p").lstrip("0")
            start_period  = cursor.strftime("%p")
            end_period    = end_cursor.strftime("%p")
            if start_period == end_period:
                slot_str = f"{cursor.strftime('%I:%M').lstrip('0')}-{end_str}"
            else:
                slot_str = f"{start_str}-{end_str}"
            all_slots.append((cursor, slot_str))
            cursor += timedelta(minutes=duration)

        # ── Filter busy slots ─────────────────────────────────────────────────
        if busy_periods:
            slots = [s for dt, s in all_slots if not is_slot_busy(dt, duration, busy_periods)]
        else:
            slots = [s for _, s in all_slots]

        # ── Fallback: if all slots filtered (suspicious — past dates / token expired)
        # return all slots without filtering to avoid blocking the candidate
        if not slots and all_slots:
            print(f"[SLOTS] FreeBusy filtered all slots — returning unfiltered as fallback")
            slots = [s for _, s in all_slots]

        print(f"[SLOTS] Window: {start_time_str} → {end_time_str} | Duration: {duration}min")
        print(f"[SLOTS] Total generated: {len(all_slots)} | After filter: {len(slots)}")
        print(f"[SLOTS] {len(slots)} available slot(s) for {date_str}")

        return slots

    except Exception as e:
        print(f"[SLOTS] Generation error: {e}")
        return []


def parse_date_with_llm(user_input: str, available_dates: list) -> str:
    """Use LLM to parse user date input. Returns matched date or 'NO_MATCH'."""
    numbered_dates = "\n".join([f"{i}. {d}" for i, d in enumerate(available_dates, 1)])
    prompt = PARSE_DATE_PROMPT.format(
        user_input      = user_input,
        available_dates = numbered_dates
    )
    resp = evaluation_llm.invoke(prompt)
    result = resp.content.strip()
    print(f"[DATE PARSE] Input: '{user_input}' → Result: '{result}'")
    return result if result in available_dates else "NO_MATCH"


def parse_slot_with_llm(user_input: str, available_slots: list, duration: int = 30) -> str:
    """Use LLM to parse user slot input. Returns matched slot or 'NO_MATCH'."""
    numbered = "\n".join([f"{i}. {s}" for i, s in enumerate(available_slots, 1)])
    prompt   = PARSE_SLOT_PROMPT.format(
        user_input      = user_input,
        available_slots = numbered
    )
    resp   = evaluation_llm.invoke(prompt)
    result = resp.content.strip()
    print(f"[SLOT PARSE] Input: '{user_input}' → Result: '{result}'")
    return result if result in available_slots else "NO_MATCH"


def parse_confirmation_with_llm(user_input: str, context: str = "") -> str:
    """Use LLM to parse yes/no confirmation with conversational context."""
    prompt = PARSE_CONFIRMATION_PROMPT.format(
        context    = context or "User was asked to confirm their interview date and time selection.",
        user_input = user_input
    )
    resp   = evaluation_llm.invoke(prompt)
    result = resp.content.strip().upper()
    print(f"[CONFIRM PARSE] Input: '{user_input}' → Result: '{result}'")
    return result if result in ("YES", "NO", "UNCLEAR") else "UNCLEAR"


def send_interview_confirmation_email(
    candidate_email: str,
    candidate_name:  str,
    hiring_manager:  str,
    date:            str,
    slot:            str,
    duration:        int,
) -> bool:
    """Send confirmation email to candidate via Brevo."""
    try:
        import requests as _req
        import os

        body = INTERVIEW_EMAIL_BODY.format(
            candidate_name  = candidate_name,
            date            = format_date_display(date),
            time            = slot,
            hiring_manager  = hiring_manager or "Our Team",
            duration        = duration,
        )

        brevo_api_key = os.getenv("BREVO_API_KEY", "")
        if not brevo_api_key:
            print("[EMAIL] BREVO_API_KEY not set")
            return False

        payload = {
            "sender":     {"name": "Cleo HR", "email": "noreply@cleohr.com"},
            "to":         [{"email": candidate_email, "name": candidate_name}],
            "subject":    INTERVIEW_EMAIL_SUBJECT,
            "textContent": body,
        }

        resp = _req.post(
            "https://api.brevo.com/v3/smtp/email",
            json    = payload,
            headers = {
                "api-key":      brevo_api_key,
                "Content-Type": "application/json",
            },
            timeout = 10
        )

        if resp.status_code in (200, 201):
            print(f"[EMAIL] Confirmation sent to {candidate_email}")
            return True

        print(f"[EMAIL] Send failed: {resp.status_code} — {resp.text}")
        return False

    except Exception as e:
        print(f"[EMAIL] Send error: {e}")
        return False


# ==================== NODES ====================

def greeting_node(state: InterviewState) -> InterviewState:
    """Fetch candidate + interview data, greet by name, show available dates."""
    print("greeting_node called")

    candidate_id = state.get("candidate_id", "")
    is_live      = state.get("is_live", False)

    # ── Fetch candidate ───────────────────────────────────────────────────────
    if state.get("api_source") == "bubble":
        candidate = bubble_api.get_candidate_data(candidate_id)
    else:
        candidate = get_candidate(candidate_id, is_live)

    if not candidate:
        state["messages"].append(AIMessage(
            content="I'm having trouble retrieving your details. Please contact our team directly."
        ))
        state["completed"] = True
        return state

    state["candidate_name"]  = candidate.get("name", "there")
    state["candidate_email"] = candidate.get("email", "")
    state["candidate_phone"] = candidate.get("phone", "")

    # Derive timezone from candidate address state
    address = candidate.get("address", {})
    if isinstance(address, dict):
        state_code = address.get("state", "")
    else:
        # Bubble returns address as a plain string (e.g. "lahore") — no state code available
        state_code = ""
    state["timezone"] = get_timezone_from_state(state_code) if state_code else "America/New_York"
    state["candidate_state"] = state_code

    # ── Fetch interview data ──────────────────────────────────────────────────
    if state.get("api_source") == "bubble":
        interview = bubble_api.get_interview_data(candidate_id)
    else:
        interview = get_interview_data(candidate_id, is_live)

    if not interview:
        state["messages"].append(AIMessage(content=INTERVIEW_NO_DATES))
        state["completed"] = True
        return state

    state["interview_dates"]    = interview.get("interview_dates", [])
    state["interview_duration"] = interview.get("interview_duration", 30)
    state["google_auth_token"]  = interview.get("google_auth_token", "")
    state["hiring_manager_id"]  = str(interview.get("hiring_manager_id", ""))
    state["availability"]       = interview.get("availability", [])

    print(f"[INTERVIEW] Dates: {state['interview_dates']}")
    print(f"[INTERVIEW] Duration: {state['interview_duration']}")
    print(f"[INTERVIEW] Availability windows: {len(state['availability'])}")
    print(f"[INTERVIEW] Raw interview response: {interview}")

    # Booked slots fetched live via FreeBusy API per date — no pre-fetch needed
    state["booked_slots"] = []

    if not state["interview_dates"]:
        state["messages"].append(AIMessage(content=INTERVIEW_NO_DATES))
        state["completed"] = True
        return state

    # ── Only Greeting ──────────────────────────────────────────────────
    greeting = INTERVIEW_GREETING_PROMPT.format(
        candidate_name=state["candidate_name"]
    )
    state["messages"].append(AIMessage(content=greeting))

    return state

def greeting_router(state: InterviewState) -> Literal["ask_date", "__end__"]:
    print("greeting_router called")
    if state.get("completed"):
        return "__end__"
    return "ask_date"

def ask_date_node(state: InterviewState) -> InterviewState:
    """Ask or re-ask for date selection."""
    print("ask_date_node called")

    attempts   = state["re_ask_attempts"].get("date", 0)
    dates_list = format_dates_list(state["interview_dates"])

    if attempts == 0:
        # First ask — greeting already showed the list, just re-show it
        state["messages"].append(AIMessage(
            content=INTERVIEW_ASK_DATE.format(dates_list=dates_list)
        ))
    else:
        # Re-ask — reference what user said
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        state["messages"].append(AIMessage(
            content=INTERVIEW_DATE_REASK_PROMPT.format(
                user_input=user_input,
                dates_list=dates_list
            )
        ))

    return state


def store_date_node(state: InterviewState) -> InterviewState:
    """Validate date input only. No messages appended here."""
    print("store_date_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()
    print(f"[DATE] User input: '{user_input}'")

    # ── Detect explicit decline ───────────────────────────────────────────────
    declining_phrases = [
        "none", "no date", "doesn't work", "don't work", "not work",
        "none of", "nothing works", "can't make", "cannot make",
        "not available", "none work", "no above"
    ]
    if any(phrase in user_input.lower() for phrase in declining_phrases):
        state["messages"].append(AIMessage(
            content=(
                "I'm sorry to hear that none of the available dates work for you. 😔\n\n"
                "Please reach out to our hiring team directly to arrange a suitable time. "
                "They'll be happy to find an alternative that works for you!"
            )
        ))
        state["completed"] = True
        return state

    # ── Parse with LLM ────────────────────────────────────────────────────────
    matched_date = parse_date_with_llm(user_input, state["interview_dates"])

    if matched_date == "NO_MATCH":
        attempts = state["re_ask_attempts"].get("date", 0) + 1
        state["re_ask_attempts"]["date"] = attempts
        print(f"[DATE] No match, attempt {attempts}")

        if attempts >= 3:
            state["re_ask_attempts"].pop("date", None)
            state["messages"].append(AIMessage(content=INTERVIEW_MAX_ATTEMPTS))
            state["completed"] = True

        return state

    # ── Valid — generate slots ────────────────────────────────────────────────
    state["re_ask_attempts"].pop("date", None)
    state["selected_date"] = matched_date
    print(f"[DATE] Selected: {matched_date}")

    slots = generate_slots(
        date_str     = matched_date,
        availability = state["availability"],
        duration     = state["interview_duration"],
        auth_token   = state["google_auth_token"],
        timezone     = state["timezone"],
    )

    if not slots:
        state["messages"].append(AIMessage(
            content=(
                f"Sorry, there are no available slots for {format_date_display(matched_date)}. "
                f"Please choose a different date from the list above."
            )
        ))
        state["selected_date"] = ""
        return state

    state["available_slots"] = slots
    return state


def date_router(state: InterviewState) -> Literal["ask_slot", "ask_date", "__end__"]:
    print("date_router called")

    if state.get("completed"):
        return "__end__"

    if state.get("selected_date") and state.get("available_slots"):
        return "ask_slot"

    return "ask_date"


def ask_slot_node(state: InterviewState) -> InterviewState:
    """Ask or re-ask for slot selection."""
    print("ask_slot_node called")

    attempts   = state["re_ask_attempts"].get("slot", 0)
    slots_list = format_slots_list(state["available_slots"], state["interview_duration"])

    # Coming back from confirmation rejection
    if state.get("reselecting_slot"):
        state["reselecting_slot"] = False
        state["messages"].append(AIMessage(
            content=f"{INTERVIEW_RESELECT}\n\n{slots_list}"
        ))
        return state

    if attempts == 0:
        state["messages"].append(AIMessage(
            content=INTERVIEW_ASK_SLOT.format(
                selected_date=format_date_display(state["selected_date"]),
                slots_list=slots_list
            )
        ))
    else:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        state["messages"].append(AIMessage(
            content=INTERVIEW_SLOT_REASK_PROMPT.format(
                user_input=user_input,
                slots_list=slots_list
            )
        ))

    return state


def store_slot_node(state: InterviewState) -> InterviewState:
    """Parse and validate candidate's slot selection."""
    print("store_slot_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()
    print(f"[SLOT] User input: '{user_input}'")

    # ── Parse with LLM ───────────────────────────────────────────────────────
    matched_slot = parse_slot_with_llm(user_input, state["available_slots"])

    if matched_slot == "NO_MATCH":
        attempts = state["re_ask_attempts"].get("slot", 0) + 1
        state["re_ask_attempts"]["slot"] = attempts
        print(f"[SLOT] No match, attempt {attempts}")

        declining_phrases = [
            "none", "no slot", "doesn't work", "don't work", "not work",
            "nothing works", "can't make", "cannot make", "not available",
            "none work", "no time", "no above", "nothing"
        ]
        is_declining = any(phrase in user_input.lower() for phrase in declining_phrases)

        if is_declining or attempts >= 3:
            state["re_ask_attempts"].pop("slot", None)
            state["messages"].append(AIMessage(
                content=(
                    "I'm sorry none of the available time slots work for you. 😔\n\n"
                    "Please reach out to our hiring team directly and they'll find "
                    "a time that works for you!"
                )
            ))
            state["completed"] = True

        return state

    # ── Valid slot ────────────────────────────────────────────────────────────
    state["re_ask_attempts"].pop("slot", None)
    state["selected_slot"] = matched_slot
    print(f"[SLOT] Selected: {matched_slot}")

    return state


def slot_router(state: InterviewState) -> Literal["ask_confirmation", "ask_slot", "__end__"]:
    print("slot_router called")

    if state.get("completed"):
        return "__end__"

    if state.get("selected_slot"):
        return "ask_confirmation"

    return "ask_slot"


def ask_confirmation_node(state: InterviewState) -> InterviewState:
    """Ask or re-ask for confirmation."""
    print("ask_confirmation_node called")

    attempts = state["re_ask_attempts"].get("confirm", 0)

    if attempts == 0:
        state["messages"].append(AIMessage(
            content=INTERVIEW_CONFIRM_PROMPT.format(
                candidate_name=state["candidate_name"],
                selected_date =format_date_display(state["selected_date"]),
                selected_slot =state["selected_slot"],
                duration      =state["interview_duration"],
            )
        ))
    else:
        state["messages"].append(AIMessage(content=INTERVIEW_CONFIRM_REASK))

    return state


def store_confirmation_node(state: InterviewState) -> InterviewState:
    """Validate confirmation only. No messages except terminal cases."""
    print("store_confirmation_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()
    context    = (
        f"The candidate was asked to confirm their interview scheduled for "
        f"{format_date_display(state['selected_date'])} at {state['selected_slot']} "
        f"({state['interview_duration']} minutes). Shall I confirm this?"
    )
    result = parse_confirmation_with_llm(user_input, context)

    if result == "YES":
        state["confirmed"] = True
        return state

    if result == "NO":
        # Reset slot — ask_slot_node will handle the message
        state["selected_slot"] = ""
        state["reselecting_slot"] = True
        state["re_ask_attempts"].pop("slot", None)
        state["re_ask_attempts"].pop("confirm", None)
        return state

    # UNCLEAR
    attempts = state["re_ask_attempts"].get("confirm", 0) + 1
    state["re_ask_attempts"]["confirm"] = attempts

    if attempts >= 3:
        state["re_ask_attempts"].pop("confirm", None)
        state["messages"].append(AIMessage(content=INTERVIEW_MAX_ATTEMPTS))
        state["completed"] = True

    return state



def confirmation_router(state: InterviewState) -> Literal["create_event", "ask_slot", "ask_confirmation", "__end__"]:
    print("confirmation_router called")

    if state.get("completed"):
        return "__end__"

    if state.get("confirmed"):
        return "create_event"

    # No slot selected — go back to slot selection
    if not state.get("selected_slot"):
        return "ask_slot"

    # Still waiting for confirmation
    return "ask_confirmation"


def create_event_node(state: InterviewState) -> InterviewState:
    """Create Google Calendar event."""
    print("create_event_node called")

    event_id = create_interview_event(
        auth_token      = state["google_auth_token"],
        candidate_name  = state["candidate_name"],
        candidate_email = state["candidate_email"],
        date            = state["selected_date"],
        slot            = state["selected_slot"],
        duration        = state["interview_duration"],
        timezone        = state["timezone"],
        hiring_manager  = state.get("hiring_manager", ""),
    )

    if not event_id:
        print(f"[CALENDAR] Event creation failed — using fallback for testing")
        state["event_id"] = "test_event_" + state["session_id"][:8]
        # In production remove above line and uncomment below:
        # state["messages"].append(AIMessage(content=INTERVIEW_CALENDAR_ERROR))
        # state["completed"] = True
        # return state
    else:
        state["event_id"] = event_id
        print(f"[INTERVIEW] Google Calendar event created: {event_id}")

    return state


def post_schedule_node(state: InterviewState) -> InterviewState:
    """POST confirmed slot to Xano."""
    print("post_schedule_node called")

    if not state.get("event_id"):
        return state

    if state.get("api_source") == "bubble":
        success = bubble_api.post_interview_schedule(
            candidate_id = state["candidate_id"],
            date         = state["selected_date"],
            time         = state["selected_slot"],
            event_id     = state["event_id"],
        )
    else:
        success = post_schedule(
            candidate_id = state["candidate_id"],
            date         = state["selected_date"],
            time         = state["selected_slot"],
            event_id     = state["event_id"],
            is_live      = state.get("is_live", False),
    )

    if not success:
        print(f"[INTERVIEW] Xano schedule post failed — continuing anyway")

    return state

def create_event_router(state: InterviewState) -> Literal["post_schedule", "__end__"]:
    print("create_event_router called")
    if state.get("completed") or not state.get("event_id"):
        return "__end__"
    return "post_schedule"

def send_email_node(state: InterviewState) -> InterviewState:
    """Send confirmation email to candidate via Brevo."""
    print("send_email_node called")

    success = send_interview_confirmation_email(
        candidate_email = state["candidate_email"],
        candidate_name  = state["candidate_name"],
        hiring_manager  = state.get("hiring_manager", "Our Team"),
        date            = state["selected_date"],
        slot            = state["selected_slot"],
        duration        = state["interview_duration"],
    )

    state["email_sent"] = success
    return state


def final_node(state: InterviewState) -> InterviewState:
    """Send final confirmation message."""
    print("final_node called")

    state["messages"].append(AIMessage(
        content=INTERVIEW_SUCCESS_PROMPT.format(
            candidate_name=state["candidate_name"],
            selected_date =format_date_display(state["selected_date"]),
            selected_slot =state["selected_slot"],
        )
    ))
    state["completed"] = True
    return state


# ==================== GRAPH BUILDER ====================

def build_interview_graph(checkpointer):
    """Build the Cleo Interview Scheduling LangGraph."""
    workflow = StateGraph(InterviewState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    workflow.add_node("greeting",           greeting_node)
    workflow.add_node("ask_date", ask_date_node)
    workflow.add_node("store_date",         store_date_node)
    workflow.add_node("ask_slot",           ask_slot_node)
    workflow.add_node("store_slot",         store_slot_node)
    workflow.add_node("ask_confirmation",   ask_confirmation_node)
    workflow.add_node("store_confirmation", store_confirmation_node)
    workflow.add_node("create_event",       create_event_node)
    workflow.add_node("post_schedule",      post_schedule_node)
    workflow.add_node("send_email",         send_email_node)
    workflow.add_node("final",              final_node)

    # ── Entry ─────────────────────────────────────────────────────────────────
    workflow.set_entry_point("greeting")

    # ── Edges ─────────────────────────────────────────────────────────────────
    workflow.add_conditional_edges("greeting", greeting_router)
    workflow.add_edge("ask_date",           "store_date")
    workflow.add_conditional_edges("store_date", date_router)
    workflow.add_edge("ask_slot",           "store_slot")
    workflow.add_conditional_edges("store_slot", slot_router)
    workflow.add_edge("ask_confirmation",   "store_confirmation")
    workflow.add_conditional_edges("store_confirmation", confirmation_router)
    workflow.add_conditional_edges("create_event", create_event_router)
    workflow.add_edge("post_schedule",      "send_email")
    workflow.add_edge("send_email",         "final")
    workflow.add_edge("final",              END)

    # ── Compile ───────────────────────────────────────────────────────────────
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=[
            "ask_date",
            "ask_slot",
            "ask_confirmation",
        ]
    )

    return app
