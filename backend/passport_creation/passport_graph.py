"""
Passport Graph — Cleo Work Passport™
Separate LangGraph for role-agnostic candidate profile builder.
Shares utility functions from graph.py but has its own state, nodes, and edges.
"""

import json
import time
import re
from datetime import datetime
from typing import Literal, List, Dict

from langgraph.graph import StateGraph, END, MessagesState
from langgraph.types import interrupt
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from langchain.prompts import ChatPromptTemplate

import phonenumbers
from dotenv import load_dotenv

# ── Shared utilities from existing codebase ───────────────────────────────────
from prompts1 import (
    SYSTEM_PROMPT,
    PERSONAL_DETAIL_ASK_PROMPT,
    PERSONAL_DETAIL_REASK_PROMPT,
    PERSONAL_DETAIL_REASK_WITH_EXAMPLE_PROMPT,
    CONSENT_EVALUATION_PROMPT,
)
from candidate_helpers import extract_email_from_text, extract_phone_from_text
from otp_verification import (
    generate_otp,
    send_email_otp,
    verify_otp,
    is_otp_expired,
    create_phone_verify_session,
    validate_phone_otp,
)
from id_verification import create_id_verify_session, save_session_mapping
import cleo_engagement

# ── Passport-specific imports ─────────────────────────────────────────────────
from passport_creation.passport_configs import PASSPORT_CONFIG
from passport_creation.passport_prompts import (
    PASSPORT_GREETING_BUBBLE_1,
    PASSPORT_GREETING_BUBBLE_2,
    PASSPORT_GREETING_BUBBLE_3,
    PASSPORT_ASK_SHIFT,
    PASSPORT_POST_NAME_PROMPT,
    PASSPORT_SHIFT_CONFIRMED,
    PASSPORT_SHIFT_NONE_SELECTED,
    PASSPORT_ASK_LOCATION,
    PASSPORT_LOCATION_CONFIRMED_PROMPT,
    PASSPORT_SCREENING_ACK_PROMPT,
    PASSPORT_PRE_CONTACT_MESSAGE,
    PASSPORT_ASK_WORK_HISTORY,
    PASSPORT_ASK_MILITARY,
    PASSPORT_MILITARY_THANKS,
    PASSPORT_WRAP_W1,
    PASSPORT_WRAP_W2,
    PASSPORT_WRAP_W3,
    PASSPORT_PROFILE_PROMPT,
    PASSPORT_SUMMARY_PROMPT
)
from passport_creation.xano_passport import create_candidate_account, create_passport_record, update_passport_section
from graph import interpret_response, generate_reask_message

load_dotenv()

# ── LLM setup ─────────────────────────────────────────────────────────────────
llm            = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)
evaluation_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

chat_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{user_input}")
])

# ── Validation helpers ────────────────────────────────────────────────────────

def validate_email(email: str) -> bool:
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def validate_phone(phone: str) -> bool:
    try:
        parsed = phonenumbers.parse(phone, None)
        return phonenumbers.is_valid_number(parsed)
    except Exception:
        return False


# ==================== PASSPORT STATE ====================

class PassportState(MessagesState):
    """State for the Cleo Work Passport flow"""

    # ── Session ───────────────────────────────────────────────────────────────
    session_id:      str  = ""
    is_live:         bool = False

    # ── Passport record ───────────────────────────────────────────────────────
    passport_id:     str  = ""     # Xano passport record ID (set after POST)
    passport_link:   str  = ""      # Shareable link returned by Xano on POST

    # ── Accumulated passport profile (built section by section) ───────────────
    passport_profile: Dict = {}

    # ── Privacy consent ───────────────────────────────────────────────────────
    privacy_consented:        bool = False
    show_privacy_consent_ui:  bool = False

    # ── Personal details ──────────────────────────────────────────────────────
    personal_details: Dict[str, str] = {}

    # ── Knockout (eligibility) ────────────────────────────────────────────────
    knockout_questions:             List[str]       = []
    knockout_answers:               Dict[str, str]  = {}
    current_knockout_question_index: int            = 0
    knockout_passed:                bool            = False
    current_knockout_failed:        bool            = False

    # ── Shift preferences ─────────────────────────────────────────────────────
    shift_preferences: List[str] = []

    # ── Location ──────────────────────────────────────────────────────────────
    address:          Dict[str, str] = {}   # { city, state, zip, full }
    commute_method:   str            = ""
    show_address_ui:  bool           = False

    # ── Screening questions (Q5–Q8) ───────────────────────────────────────────
    questions:             List[str]       = []
    answers:               Dict[str, str]  = {}
    current_question_index: int            = 0
    scoring_model:         Dict[str, Dict] = {}

    # ── Email ─────────────────────────────────────────────────────────────────
    email_validation_failed:  bool = False
    invalid_email_attempt:    str  = ""
    email_attempt_count:      int  = 0
    email_hard_stop:          bool = False
    email_otp_code:           str  = ""
    email_otp_sent:           bool = False
    email_otp_sent_failed:    bool = False
    email_otp_timestamp:      float = 0
    email_verified:           bool = False
    email_otp_attempts:       int  = 0

    # ── Phone ─────────────────────────────────────────────────────────────────
    phone_validation_failed:  bool  = False
    invalid_phone_attempt:    str   = ""
    phone_attempt_count:      int   = 0
    phone_otp_code:           str   = ""
    phone_otp_sent:           bool  = False
    phone_otp_sent_failed:    bool  = False
    phone_otp_timestamp:      float = 0
    phone_verified:           bool  = False
    phone_otp_attempts:       int   = 0
    phone_verify_session_uuid: str  = ""

    # ── Work history ──────────────────────────────────────────────────────────
    work_experience:       List[Dict[str, str]] = []
    show_work_experience_ui: bool              = False

    # ── Education ─────────────────────────────────────────────────────────────
    education_level:   str  = ""
    show_education_ui: bool = False

    # ── Military ──────────────────────────────────────────────────────────────
    military_served:       bool            = False
    military_details:      Dict[str, str]  = {}
    military_follow_up_done: bool          = False

    # ── ID Verification ───────────────────────────────────────────────────────
    id_verify_link:       str  = ""
    id_verify_session_id: str  = ""
    id_verified:          bool = False
    id_verify_failed:     bool = False
    show_id_verify_ui:    bool = False

    # ── Re-ask tracking ───────────────────────────────────────────────────────
    re_ask_attempts: Dict[str, int] = {}
    answer_reask_reason: str = ""
    kq_reask_reason: str = ""

    passport_address_mode: bool = False
    professional_summary:  str  = ""


# ==================== XANO PATCH HELPER ====================

def passport_patch(state: PassportState, section: str, data: dict):
    """Fire-and-forget PATCH to Xano passport table. Never crashes the graph."""
    passport_id = state.get("passport_id", 0)
    is_live     = state.get("is_live", False)

    print(f"[PASSPORT] PATCH '{section}': {data}")
    if passport_id:
        update_passport_section(passport_id, section, data, is_live)
    else:
        print(f"[PASSPORT] Skipping PATCH '{section}' — no passport_id yet")


# ==================== GREETING ====================

def passport_greeting_node(state: PassportState) -> PassportState:
    """Send 3 staggered greeting bubbles. Third bubble triggers privacy consent checkbox UI."""
    print("passport_greeting_node called")

    state["messages"].append(AIMessage(content=PASSPORT_GREETING_BUBBLE_1))
    state["messages"].append(AIMessage(content=PASSPORT_GREETING_BUBBLE_2))
    state["messages"].append(AIMessage(content=PASSPORT_GREETING_BUBBLE_3))
    state["show_privacy_consent_ui"] = True

    return state


def store_privacy_consent_node(state: PassportState) -> PassportState:
    """Store privacy consent checkbox confirmation."""
    print("store_privacy_consent_node called")

    messages    = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip().lower()

        # Accept checkbox confirmation or any affirmative response
        result = evaluation_llm.invoke(
            f'Did the user agree or consent? Answer ONLY "yes" or "no".\nInput: "{user_input}"'
        )
        if result.content.strip().lower() == "yes":
            state["privacy_consented"] = True
            state["messages"].append(AIMessage(
                content="Let's get started! First things first — what is your full name?"
            ))
        else:
            state["messages"].append(AIMessage(
                content="No problem at all! Your privacy is important to us. Feel free to come back anytime. 😊"
            ))

    return state


def privacy_router(state: PassportState) -> Literal["ask_name", "__end__"]:
    if state.get("privacy_consented"):
        return "ask_name"
    return "__end__"


# ==================== NAME ====================

def ask_name_node(state: PassportState) -> PassportState:
    print("ask_name_node called")

    # ── Re-ask if previous attempt was invalid ────────────────────────────────
    if state.get("re_ask_attempts", {}).get("name", 0) > 0:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        reask = generate_reask_message(
            "What is your full name?",
            user_input,
            reason="gibberish",
            conversation_history=state["messages"]
        )
        state["messages"].append(AIMessage(content=reask))

    # First visit — message already sent by store_privacy_consent_node
    return state


def store_name_node(state: PassportState) -> PassportState:
    print("store_name_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()

    # ── Validate name ─────────────────────────────────────────────────────────
    prompt = f"""Does this input look like a human name?

Input: "{user_input}"

Return YES if:
- It has at least two words
- The words contain mostly letters (spaces, hyphens, apostrophes allowed)

Return NO only if:
- It is clearly random characters (e.g. "asdfgh", "123abc")
- It is a single word with no last name AND it looks like gibberish
- Single common first names like "John" or "Maria" alone are NO (need last name)

Return ONLY "YES" or "NO". Nothing else."""

    response = evaluation_llm.invoke(prompt)
    is_valid = response.content.strip().upper() == "YES"

    if not is_valid:
            attempts = state["re_ask_attempts"].get("name", 0) + 1
            state["re_ask_attempts"]["name"] = attempts
            print(f"[NAME] Invalid name, attempt {attempts}: {user_input}")

            if attempts >= 3:
                state["re_ask_attempts"].pop("name", None)
                state["personal_details"]["name"] = "__end__"  # signal name_router to end
                state["messages"].append(AIMessage(
                    content="Thank you so much for taking the time to apply! We're unable to complete your application right now, but one of our team members will reach out to you shortly. 😊"
                ))
            return state

    print(f"[NAME] Valid name: {user_input}")
    state["personal_details"]["name"] = user_input
    state["re_ask_attempts"].pop("name", None)

    # Warm acknowledgement
    first_name = user_input.split()[0]
    state["messages"].append(AIMessage(content=f"Great to meet you, {first_name}! Let's make sure we have the basics covered first."))

    return state


def name_router(state: PassportState) -> Literal["ask_name", "ask_knockout_question", "__end__"]:
    name = state.get("personal_details", {}).get("name", "")
    if name == "__end__":
        return "__end__"
    if not name:
        return "ask_name"
    return "ask_knockout_question"


# ==================== KNOCKOUT QUESTIONS ====================

def ask_knockout_question_node(state: PassportState) -> PassportState:
    print("ask_knockout_question_node called")

    idx               = state["current_knockout_question_index"]
    knockout_questions = state["knockout_questions"]

    if idx >= len(knockout_questions):
        return state

    knockout_question = knockout_questions[idx]

    # ── Re-ask with dynamic message ───────────────────────────────────────────
    if knockout_question in state.get("re_ask_attempts", {}):
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        reason     = state.get("kq_reask_reason", "gibberish")
        reask      = generate_reask_message(knockout_question, user_input, reason, conversation_history=state["messages"])
        state["messages"].append(AIMessage(content=reask))
        return state

    # ── Initial ask ───────────────────────────────────────────────────────────
    state["messages"].append(AIMessage(content=knockout_question))
    return state


def store_kq_answer_node(state: PassportState) -> PassportState:
    print("store_kq_answer_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    return state


def evaluate_single_knockout_node(state: PassportState) -> PassportState:
    print("evaluate_single_knockout_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    idx = state["current_knockout_question_index"]
    if idx >= len(state["knockout_questions"]):
        return state

    knockout_question = state["knockout_questions"][idx]

    # ── Use interpret_response for robust evaluation ──────────────────────────
    result   = interpret_response(knockout_question, last_message.content, "yes_no")
    resolved = result["resolved_intent"]
    print(f"[KQ] interpret result: {result}")

    if resolved == "ambiguous":
        attempts = state["re_ask_attempts"].get(knockout_question, 0) + 1
        state["re_ask_attempts"][knockout_question] = attempts
        state["kq_reask_reason"] = result["reask_reason"]
        print(f"[KQ] Ambiguous attempt {attempts}")

        if attempts >= 3:
            print(f"[KQ] 3 ambiguous attempts — defaulting to no")
            state["knockout_answers"][knockout_question] = "no"
            state["current_knockout_failed"] = True
            state["re_ask_attempts"].pop(knockout_question, None)
            state["current_knockout_question_index"] += 1
            end_message = PASSPORT_CONFIG["knockout_end_messages"].get(
                knockout_question,
                "Thank you for your time! Unfortunately we're unable to proceed at this stage."
            )
            state["messages"].append(AIMessage(content=end_message))
        return state

    # ── Clear answer ──────────────────────────────────────────────────────────
    state["knockout_answers"][knockout_question] = result["clean"]
    state["re_ask_attempts"].pop(knockout_question, None)
    state["current_knockout_question_index"] += 1

    if resolved == "no":
        state["current_knockout_failed"] = True
        end_message = PASSPORT_CONFIG["knockout_end_messages"].get(
            knockout_question,
            "Thank you for your time! Unfortunately we're unable to proceed at this stage."
        )
        state["messages"].append(AIMessage(content=end_message))
    else:
        state["current_knockout_failed"] = False
        # Flag caveats for record
        if result.get("should_flag") and result.get("flag_note"):
            print(f"[KQ] Caveat noted: {result['flag_note']}")

        ack_messages = ["Got it, thank you. ✅", "Great. Let's keep going!"]
        ack = ack_messages[idx] if idx < len(ack_messages) else ""
        if ack:
            state["messages"].append(AIMessage(content=ack))

    return state

def single_knockout_router(state: PassportState) -> Literal["ask_knockout_question", "ask_shift_preference", "__end__"]:
    print("single_knockout_router called")

    if state.get("current_knockout_failed"):
        return "__end__"

    if state["current_knockout_question_index"] < len(state["knockout_questions"]):
        return "ask_knockout_question"

    # All KQs passed → ask shift preference
    return "ask_shift_preference"


# ==================== SHIFT PREFERENCE ====================

def ask_shift_preference_node(state: PassportState) -> PassportState:
    """Send shift preference question with checkbox UI."""
    print("ask_shift_preference_node called")

    state["messages"].append(AIMessage(content=PASSPORT_ASK_SHIFT))
    # Frontend renders checkboxes for: Days, Evenings, Overnights, Weekends
    # Selection arrives as JSON string: '["Days", "Evenings"]'

    return state


def store_shift_preference_node(state: PassportState) -> PassportState:
    """Store selected shifts. Re-ask if nothing selected."""
    print("store_shift_preference_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        try:
            selected = json.loads(last_message.content)
            if isinstance(selected, list) and len(selected) > 0:
                state["shift_preferences"] = selected
                state["messages"].append(AIMessage(content=PASSPORT_SHIFT_CONFIRMED))
            else:
                state["messages"].append(AIMessage(content=PASSPORT_SHIFT_NONE_SELECTED))
        except Exception:
            # Plain text fallback — extract shifts using LLM
            prompt = f"""Extract shift preferences from this text. 
Valid options: Days, Evenings, Overnights, Weekends.
Text: "{last_message.content}"
Return ONLY a JSON array. Example: ["Days", "Evenings"]"""
            response = llm.invoke([HumanMessage(content=prompt)])
            try:
                shifts = json.loads(response.content.strip())
                state["shift_preferences"] = shifts if isinstance(shifts, list) else []
                state["messages"].append(AIMessage(content=PASSPORT_SHIFT_CONFIRMED))
            except Exception:
                state["shift_preferences"] = []
                state["messages"].append(AIMessage(content=PASSPORT_SHIFT_NONE_SELECTED))

    return state


def shift_router(state: PassportState) -> Literal["ask_shift_preference", "ask_address"]:
    if not state.get("shift_preferences"):
        return "ask_shift_preference"
    return "ask_address"


# ==================== ADDRESS (ZIP/CITY + COMMUTE) ====================

def ask_address_node(state: PassportState) -> PassportState:
    """Ask for ZIP/city and commute method. Also POST passport record to Xano."""
    print("ask_address_node called")

    # ── POST: Create passport record now ────────────────────────────────────
    if not state.get("passport_id"):
        passport_id = create_passport_record(
            session_id=state.get("session_id", ""),
            is_live=state.get("is_live", False),
        )
        state["passport_id"] = passport_id
        print(f"[PASSPORT] Record created — ID: {passport_id}")
    # ─────────────────────────────────────────────────────────────────────────

    state["messages"].append(AIMessage(content=PASSPORT_ASK_LOCATION))
    state["show_address_ui"] = True
    state["passport_address_mode"] = True   # signals frontend: ZIP/city only

    return state


def store_address_node(state: PassportState) -> PassportState:
    """Parse location and commute method from candidate response."""
    print("store_address_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content.strip()

        # Try JSON first (from address autocomplete UI)
        try:
            address_data = json.loads(user_text)
            state["address"] = address_data
            state["commute_method"] = address_data.get("commute", "")
        except Exception:
            # Plain text — use LLM to extract location and commute
            prompt = f"""Extract location and commute method from this text.
Text: "{user_text}"
Return ONLY valid JSON: {{"location": "city, state or ZIP", "commute": "driving/transit/other"}}
If commute is unclear use "not specified"."""
            response = llm.invoke([HumanMessage(content=prompt)])
            try:
                extracted = json.loads(response.content.strip())
                state["address"]       = {"full": extracted.get("location", user_text)}
                state["commute_method"] = extracted.get("commute", "not specified")
            except Exception:
                state["address"]       = {"full": user_text}
                state["commute_method"] = "not specified"

        # Warm confirmation
        prompt   = PASSPORT_LOCATION_CONFIRMED_PROMPT.format(
            location=state["address"].get("full", user_text)
        )
        response = llm.invoke(prompt)
        state["messages"].append(AIMessage(content=response.content))

        # ── PATCH: KQ answers + shift preferences + location ─────────────────
        state["passport_profile"].update({
                    "eligibility":     {q: a for q, a in state.get("knockout_answers", {}).items()},
                    "shift_prefrence": state.get("shift_preferences", []),
                    "location":        state["address"],
                    "commute_method":  state["commute_method"],
        })
        passport_patch(state, "location_complete", {
                    "shift_prefrence":  state["shift_preferences"],
                    "location":         state["address"],
                    "passport_profile": state["passport_profile"],
        })
        # ─────────────────────────────────────────────────────────────────────

    return state


# ==================== SCREENING QUESTIONS (Q5–Q8) ====================

def ask_question_node(state: PassportState) -> PassportState:
    """Ask next screening question with warm acknowledgement of previous answer."""
    print("ask_question_node called")

    idx       = state["current_question_index"]
    questions = state["questions"]

    if idx >= len(questions):
        return state

    question   = questions[idx]
    first_name = state["personal_details"].get("name", "").split()[0] or "there"

    # ── Re-ask with dynamic message ───────────────────────────────────────────
    if question in state.get("re_ask_attempts", {}):
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        reason     = state.get("answer_reask_reason", "gibberish")
        reask      = generate_reask_message(question, user_input, reason, conversation_history=state["messages"])
        state["messages"].append(AIMessage(content=reask))
        return state

    # ── Initial ask ───────────────────────────────────────────────────────────
    if idx == 0:
        state["messages"].append(AIMessage(content=question))
    else:
        prev_question = questions[idx - 1]
        prev_answer   = state["answers"].get(prev_question, "")
        prompt = PASSPORT_SCREENING_ACK_PROMPT.format(
            question=prev_question,
            answer=prev_answer,
            first_name=first_name
        )
        ack = llm.invoke(prompt)
        state["messages"].append(AIMessage(content=ack.content))
        state["messages"].append(AIMessage(content=question))

    return state


def store_answer_node(state: PassportState) -> PassportState:
    """Store screening question answer using interpret_response."""
    print("store_answer_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    idx = state["current_question_index"]
    if idx >= len(state["questions"]):
        return state

    question = state["questions"][idx]

    # ── Interpret response ────────────────────────────────────────────────────
    result   = interpret_response(question, last_message.content, "open_ended")
    resolved = result["resolved_intent"]
    print(f"[ANSWER] interpret result: {result}")

    # ── Ambiguous path ────────────────────────────────────────────────────────
    if resolved == "ambiguous":
        state["answer_reask_reason"] = result["reask_reason"]
        attempts = state["re_ask_attempts"].get(question, 0) + 1
        state["re_ask_attempts"][question] = attempts

        # Accumulate partial answers across attempts
        existing = state["answers"].get(question, "")
        combined = f"{existing} {last_message.content}".strip() if existing else last_message.content
        state["answers"][question] = combined

        if attempts >= 3:
            print(f"[ANSWER] 3 ambiguous attempts — moving on with combined: {combined}")
            state["current_question_index"] += 1
            state["re_ask_attempts"].pop(question, None)

        return state

    # ── Clear answer ──────────────────────────────────────────────────────────
    state["answers"][question] = result["clean"]
    state["current_question_index"] += 1
    state["re_ask_attempts"].pop(question, None)

    return state


def question_router(state: PassportState) -> Literal["ask_question", "ask_email"]:
    """All screening questions done → move to contact verification."""
    print("question_router called")

    if state["current_question_index"] < len(state["questions"]):
        return "ask_question"

    return "ask_email"


# ==================== EMAIL ====================

def ask_email_node(state: PassportState) -> PassportState:
    print("ask_email_node called")

    # ── First time here — send transition message + PATCH screening answers ───
    if not state.get("email_otp_sent") and not state.get("email_validation_failed") and "email_refusal" not in state.get("re_ask_attempts", {}):
        if not state.get("personal_details", {}).get("email"):
            state["passport_profile"].update({
                "screening_answers": state.get("answers", {}),
            })
            passport_patch(state, "screening_complete", {
                "passport_profile": state["passport_profile"]
            })
            state["messages"].append(AIMessage(content=PASSPORT_PRE_CONTACT_MESSAGE))
    # ─────────────────────────────────────────────────────────────────────────

    if state.get("email_validation_failed"):
        if state.get("email_attempt_count", 0) >= 3:
            prompt = PERSONAL_DETAIL_REASK_WITH_EXAMPLE_PROMPT.format(
                detail_type="email",
                invalid_attempt=state.get("invalid_email_attempt"),
                example="john.doe@example.com"
            )
        else:
            prompt = PERSONAL_DETAIL_REASK_PROMPT.format(
                detail_type="email",
                invalid_attempt=state.get("invalid_email_attempt")
            )
    else:
        if state.get("email_otp_sent_failed"):
            state["messages"].append(AIMessage(
                content="Kindly enter your email address again (example: john.doe@example.com)"
            ))
            state["email_otp_sent_failed"] = False
            return state
                
        state["messages"].append(AIMessage(content="Let's lock down your secure login information. What is the best email address to attach to your permanent Candidate Passport?"))

        return state

    messages = chat_template.format_messages(user_input=prompt)
    response = llm.invoke(messages)
    state["messages"].append(AIMessage(content=response.content))

    return state


def store_email_node(state: PassportState) -> PassportState:
    print("store_email_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content.strip()
        print(f"Original input: {user_text}")

        # Skip refusal detection if input looks like an email
        if not extract_email_from_text(user_text):
            result = interpret_response("Can you provide your email address?", user_text, "yes_no")
            print(f"[EMAIL] Intent: {result['intent']}")
        else:
            result = {"resolved_intent": "yes"}

        if result["resolved_intent"] == "no":
            refusal_attempts = state.get("re_ask_attempts", {}).get("email_refusal", 0) + 1
            state["re_ask_attempts"]["email_refusal"] = refusal_attempts

            if refusal_attempts >= 2:
                state["email_hard_stop"] = True
                state["re_ask_attempts"].pop("email_refusal", None)
                state["messages"].append(AIMessage(
                    content="Thank you so much for taking the time to apply! We're unable to complete your application right now, but one of our team members will reach out to you shortly. 😊"
                ))
            else:
                state["messages"].append(AIMessage(
                    content="An email address is required to keep your Passport active and receive job match alerts. Could you please share it? (e.g. john.doe@example.com)"
                ))
            return state

        # Normal extraction path
        state["re_ask_attempts"].pop("email_refusal", None)
        email = extract_email_from_text(user_text)
        print(f"Extracted email: {email}")

        if validate_email(email):
            state["personal_details"]["email"] = email
            state["email_validation_failed"]   = False
            state["invalid_email_attempt"]     = ""
            state["email_attempt_count"]       = 0
            print("Valid email stored:", email)
        else:
            count = state.get("email_attempt_count", 0) + 1
            state["email_attempt_count"]    = count
            state["email_validation_failed"] = True
            state["invalid_email_attempt"]  = email
            print("Invalid email detected:", email)

    return state


def email_router(state: PassportState) -> Literal["ask_email", "send_email_otp", "__end__"]:
    print("email_router called")
    if state.get("email_hard_stop"):
        return "__end__"
    if state.get("re_ask_attempts", {}).get("email_refusal"):
        return "ask_email"
    if state.get("email_validation_failed"):
        return "ask_email"
    return "send_email_otp"


# ==================== EMAIL OTP ====================

def send_email_otp_node(state: PassportState) -> PassportState:
    print("send_email_otp_node called")

    email     = state["personal_details"].get("email", "")
    user_name = state["personal_details"].get("name", "")
    otp_code  = generate_otp()

    state["email_otp_code"]      = otp_code
    state["email_otp_timestamp"] = time.time()

    success = send_email_otp(email, otp_code, "Cleo Work Passport™", user_name)

    if success:
        state["email_otp_sent"] = True
        state["messages"].append(AIMessage(
            content=f"I've just sent a 6-digit verification code to {email}. Please check your inbox (and spam folder)."
        ))
    else:
        state["email_otp_sent_failed"] = True
        state["messages"].append(AIMessage(content=cleo_engagement.email_otp_failure_message))

    return state


def ask_email_otp_node(state: PassportState) -> PassportState:
    print("ask_email_otp_node called")
    state["messages"].append(AIMessage(content=cleo_engagement.ask_email_otp))
    return state


def verify_email_otp_node(state: PassportState) -> PassportState:
    print("verify_email_otp_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip()

        if user_input.lower() in ["resend", "send again", "resend code"]:
            state["email_otp_attempts"] = 0
            return state

        stored_code = state.get("email_otp_code", "")
        timestamp   = state.get("email_otp_timestamp", 0)
        is_valid, error = verify_otp(user_input, stored_code, timestamp, "email")

        if is_valid:
            state["email_verified"] = True
            state["messages"].append(AIMessage(content=cleo_engagement.email_success_message))
        else:
            state["email_otp_attempts"] += 1
            attempts = state["email_otp_attempts"]

            if error == "expired":
                state["messages"].append(AIMessage(content=cleo_engagement.otp_expired_message))
                state["email_otp_attempts"] = 0
            elif error == "invalid_format":
                state["messages"].append(AIMessage(content="Please enter a 6-digit code (numbers only)."))
            elif error == "incorrect":
                if attempts >= 3:
                    state["messages"].append(AIMessage(content=cleo_engagement.email_otp_failure_message))
                else:
                    state["messages"].append(AIMessage(
                        content=f"Hmm, that code didn't work. Please try again. (Attempt {attempts}/3)"
                    ))

    return state


def email_otp_router(state: PassportState) -> Literal["ask_phone", "send_email_otp", "ask_email", "ask_email_otp"]:
    print("email_otp_router called")

    if state.get("email_otp_sent_failed"):
        return "ask_email"
    if state.get("email_verified"):
        return "ask_phone"

    messages     = state["messages"]
    last_message = messages[-1] if messages else None
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip().lower()
        if "resend" in user_input or "send again" in user_input:
            return "send_email_otp"

    if is_otp_expired(state.get("email_otp_timestamp", 0), "email"):
        return "send_email_otp"
    if state.get("email_otp_attempts", 0) >= 3:
        state["email_otp_attempts"]    = 0
        state["email_validation_failed"] = True
        return "ask_email"

    return "ask_email_otp"


# ==================== PHONE ====================

def ask_phone_node(state: PassportState) -> PassportState:
    print("ask_phone_node called")

    if state.get("phone_validation_failed"):
        if state.get("phone_attempt_count", 0) >= 3:
            prompt = PERSONAL_DETAIL_REASK_WITH_EXAMPLE_PROMPT.format(
                detail_type="phone number",
                invalid_attempt=state.get("invalid_phone_attempt"),
                example="+1-234-567-8900"
            )
        else:
            prompt = PERSONAL_DETAIL_REASK_PROMPT.format(
                detail_type="phone number",
                invalid_attempt=state.get("invalid_phone_attempt")
            )
        messages = chat_template.format_messages(user_input=prompt)
        response = llm.invoke(messages)
        state["messages"].append(AIMessage(content=response.content))
    else:
        state["messages"].append(AIMessage(content=f"What is your phone number for hiring managers to call you for an interview?"))

    return state


def store_phone_node(state: PassportState) -> PassportState:
    print("store_phone_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content.strip()
        phone     = extract_phone_from_text(user_text)
        print(f"Original input: {user_text} | Extracted: {phone}")

        # Normalize to E.164
        if phone:
            if phone.startswith('+'):
                pass
            elif phone.startswith('0'):
                phone = '+92' + phone[1:]
            elif phone.startswith('92') or phone.startswith('1'):
                phone = '+' + phone
            else:
                phone = '+1' + phone

        if validate_phone(phone):
            state["personal_details"]["phone"]  = phone
            state["phone_validation_failed"]    = False
            state["invalid_phone_attempt"]      = ""
            state["phone_attempt_count"]        = 0
            print("Valid phone stored:", phone)
        else:
            state["phone_validation_failed"]  = True
            state["invalid_phone_attempt"]    = phone
            state["phone_attempt_count"]     += 1
            print("Invalid phone detected:", phone)

    return state


def phone_router(state: PassportState) -> Literal["ask_phone", "send_phone_otp"]:
    print("phone_router called")
    if state.get("phone_validation_failed"):
        return "ask_phone"
    return "send_phone_otp"


# ==================== PHONE OTP ====================

def send_phone_otp_node(state: PassportState) -> PassportState:
    print("send_phone_otp_node called")

    phone    = state["personal_details"].get("phone", "")
    otp_code = "123456"   # Testing mode — replace with Plivo in production
    state["phone_otp_code"] = otp_code

    state["messages"].append(AIMessage(
        content=f"I'm sending a verification text with a 6-digit code to {phone} now. Please check your messages."
    ))
    return state


def ask_phone_otp_node(state: PassportState) -> PassportState:
    print("ask_phone_otp_node called")

    if state.get("phone_otp_attempts", 0) >= 1:
        state["messages"].append(AIMessage(
            content="I can also resend the text. Just type 'resend' if needed."
        ))
    else:
        state["messages"].append(AIMessage(content=cleo_engagement.ask_phone_otp))

    return state


def verify_phone_otp_node(state: PassportState) -> PassportState:
    print("verify_phone_otp_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip()

        if user_input.lower() in ["resend", "send again", "resend code"]:
            state["phone_otp_attempts"] = 0
            return state

        stored_otp = state.get("phone_otp_code", "")
        is_valid   = (user_input == stored_otp)
        error      = "none" if is_valid else "incorrect"

        if is_valid:
            state["phone_verified"] = True

            # ── PATCH: name, email, phone now confirmed ───────────────────────
            passport_patch(state, "contact_details", {
                "name":  state["personal_details"].get("name", ""),
                "email": state["personal_details"].get("email", ""),
                "phone": state["personal_details"].get("phone", ""),
            })
            # ─────────────────────────────────────────────────────────────────
        else:
            state["phone_otp_attempts"] += 1
            attempts = state["phone_otp_attempts"]

            if error == "expired":
                state["messages"].append(AIMessage(content=cleo_engagement.otp_expired_message))
                state["phone_otp_attempts"] = 0
            elif error == "incorrect":
                if attempts >= 3:
                    state["messages"].append(AIMessage(content=cleo_engagement.phone_otp_failure_message))
                else:
                    state["messages"].append(AIMessage(
                        content=f"The code was incorrect. Please try again. (Attempt {attempts}/3)"
                    ))

    return state


def phone_otp_router(state: PassportState) -> Literal["store_work_experience_response", "send_phone_otp", "ask_phone", "ask_phone_otp"]:
    print("phone_otp_router called")

    if state.get("phone_verified"):
        return "store_work_experience_response"

    messages     = state["messages"]
    last_message = messages[-1] if messages else None
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip().lower()
        if "resend" in user_input or "send again" in user_input:
            return "send_phone_otp"

    if state.get("phone_otp_attempts", 0) >= 3:
        state["phone_otp_attempts"]    = 0
        state["phone_validation_failed"] = True
        return "ask_phone"

    return "ask_phone_otp"


# ==================== WORK HISTORY ====================

# def ask_work_experience_node(state: PassportState) -> PassportState:
#     print("ask_work_experience_node called")
#     state["messages"].append(AIMessage(content=PASSPORT_ASK_WORK_HISTORY))
#     state["show_work_experience_ui"] = True
#     return state


def store_work_experience_response_node(state: PassportState) -> PassportState:
    """trigger work experience UI."""
    print("store_work_experience_response_node called")
    
    state["messages"].append(AIMessage(content=PASSPORT_ASK_WORK_HISTORY))

    state["show_work_experience_ui"] = True

    return state


# ==================== EDUCATION ====================

def ask_education_node(state: PassportState) -> PassportState:
    print("ask_education_node called")
    state["messages"].append(AIMessage(
        content="What is the highest level of education you completed?"
    ))
    state["show_education_ui"] = True
    return state


def store_education_node(state: PassportState) -> PassportState:
    print("store_education_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        state["education_level"] = last_message.content.strip()
        state["messages"].append(AIMessage(content="Thanks! Saved. ✅"))

    print(f"Stored education level: {state['education_level']}")
    return state


# ==================== MILITARY ====================

def ask_military_node(state: PassportState) -> PassportState:
    print("ask_military_node called")

    if state.get("military_served") and not state.get("military_follow_up_done"):
        state["messages"].append(AIMessage(content=PASSPORT_MILITARY_THANKS))
    else:
        state["messages"].append(AIMessage(content=PASSPORT_ASK_MILITARY))

    return state


def store_military_node(state: PassportState) -> PassportState:
    print("store_military_node called")

    messages     = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_text = last_message.content.strip().lower()

        if not state.get("military_served"):
            result   = interpret_response(PASSPORT_ASK_MILITARY, last_message.content, "yes_no")
            resolved = result["resolved_intent"]
            if resolved == "yes":
                state["military_served"] = True
            else:
                state["military_served"]         = False
                state["military_follow_up_done"] = True
        else:
            state["military_follow_up_done"] = True
            if user_text not in ["skip", "no", "none", "n/a"]:
                state["military_details"] = {"details": last_message.content}

        # ── PATCH: work history + education + military ────────────────────────
        if state.get("military_follow_up_done") or not state.get("military_served"):
            work_experiences = state.get("work_experience", [])
            state["passport_profile"].update({
                "work_experience": [
                    {
                        "position":   exp.get("role", ""),
                        "employer":   exp.get("company", ""),
                        "startDate": exp.get("startDate", ""),
                        "endDate":   exp.get("endDate", ""),
                    }
                    for exp in work_experiences
                ],
                "education_level":  state.get("education_level", ""),
                "military_served":  state.get("military_served", False),
                "military_details": state.get("military_details", {}),
            })
            passport_patch(state, "work_history_complete", {
                "passport_profile": state["passport_profile"]
            })
        # ─────────────────────────────────────────────────────────────────────

    return state


def military_router(state: PassportState) -> Literal["ask_military", "ask_id_verification", "passport_summary"]:
    if state.get("military_served") and not state.get("military_follow_up_done"):
        return "ask_military"
    return "passport_summary"


# ==================== ID VERIFICATION ====================

async def ask_id_verification_node(state: PassportState) -> PassportState:
    print("ask_id_verification_node called")

    applicant_name   = state["personal_details"].get("name", "")
    phone            = state["personal_details"].get("phone", "")
    cleo_session_id  = state.get("session_id", "")

    verify_link, simplici_session_id = create_id_verify_session(
        cleo_session_id, applicant_name, phone
    )

    if not verify_link:
        state["id_verify_failed"] = True
        state["messages"].append(AIMessage(
            content="We're experiencing a brief technical issue with our verification system. Our team will follow up with you directly."
        ))
        return state

    state["id_verify_link"]       = verify_link
    state["id_verify_session_id"] = simplici_session_id

    await save_session_mapping(simplici_session_id, cleo_session_id)

    state["messages"].append(AIMessage(
        content="Almost there! 🏁 To protect your data and activate your Passport for hiring managers, we need a quick ID check. It takes less than 60 seconds."
    ))
    state["messages"].append(AIMessage(
        content="Please make sure you're in a well-lit room and have your government-issued ID ready. Tap the button below to start!"
    ))

    state["show_id_verify_ui"] = True

    return state


def process_id_result_node(state: PassportState) -> PassportState:
    print("process_id_result_node called")

    if state.get("id_verified"):
        state["messages"].append(AIMessage(
            content="Awesome! Your identity has been verified and secured. 🛡️"
        ))
    else:
        state["messages"].append(AIMessage(
            content="Our automated system had a brief issue confirming the verification. Don't worry — our team will review your documents and reach out if needed."
        ))

    return state


# ==================== PASSPORT SUMMARY ====================

def passport_summary_node(state: PassportState) -> PassportState:
    """Generate full passport profile JSON and PATCH to Xano. Send W1-W4 wrap-up bubbles."""
    print("passport_summary_node called")

    personal = state.get("personal_details", {})
    name     = personal.get("name", "")
    email    = personal.get("email", "")
    phone    = personal.get("phone", "")

    # Format knockout answers
    knockout_text = "\n".join([
        f"Q: {q}\nA: {a}"
        for q, a in state.get("knockout_answers", {}).items()
    ]) or "Not provided"

    # Format screening answers
    answers_text = "\n".join([
        f"Q: {q}\nA: {a}"
        for q, a in state.get("answers", {}).items()
    ]) or "Not provided"

    # Format work experience
    work_experiences = state.get("work_experience", [])
    work_exp_text = "\n".join([
        f"- {exp.get('role', '')} at {exp.get('company', '')} ({exp.get('startDate', '')} to {exp.get('endDate', '')})"
        for exp in work_experiences
    ]) if work_experiences else ""

    # Military
    military_text = ""
    if state.get("military_served"):
        details      = state.get("military_details", {})
        military_text = details.get("details", "Served — details not provided")
    else:
        military_text = "Not served"

    # Generate passport profile via LLM
    prompt = PASSPORT_PROFILE_PROMPT.format(
        name              = name,
        email             = email,
        phone             = phone,
        session_id        = state.get("session_id", ""),
        shift_preferences = json.dumps(state.get("shift_preferences", [])),
        location          = state.get("address", {}).get("full", ""),
        commute_method    = state.get("commute_method", ""),
        knockout_answers  = knockout_text,
        screening_answers = answers_text,
        work_experience   = work_exp_text,
        education         = state.get("education_level", ""),
        military          = military_text,
        current_time      = datetime.now().isoformat(),
    )

    try:
        response     = llm.invoke(prompt)
        json_text    = response.content.strip()
        if json_text.startswith("```"):
            json_text = json_text.replace("```json", "").replace("```", "").strip()
        passport_profile = json.loads(json_text)
        print("[PASSPORT] Profile generated successfully")
    except Exception as e:
        print(f"[PASSPORT] Profile generation failed: {e} — using accumulated profile")
        passport_profile = state.get("passport_profile", {})

    # Merge with accumulated profile
    state["passport_profile"].update(passport_profile)

    # Calculate fit score from profile
    fit_score = passport_profile.get("fit_score", {}).get("total_score", 0)

    # ── Generate professional summary paragraph ───────────────────────────────
    try:
        # Extract data from generated passport profile
        exp_profile   = passport_profile.get("experience_profile", {})
        fit_score     = passport_profile.get("fit_score", {})

        years_exp = exp_profile.get("years_experience", "")
        if not years_exp:
            # Calculate from work_experience dates in state
            work_exps = state.get("work_experience", [])
            if work_exps:
                total_months = 0
                for exp in work_exps:
                    try:
                        start = datetime.strptime(exp.get("startDate", ""), "%Y-%m")
                        end   = datetime.strptime(exp.get("endDate",   ""), "%Y-%m")
                        total_months += (end.year - start.year) * 12 + (end.month - start.month)
                    except Exception:
                        pass
                if total_months > 0:
                    years  = total_months // 12
                    months = total_months % 12
                    if years > 0 and months > 0:
                        years_exp = f"{years} year{'s' if years > 1 else ''} and {months} month{'s' if months > 1 else ''}"
                    elif years > 0:
                        years_exp = f"{years} year{'s' if years > 1 else ''}"
                    else:
                        years_exp = f"{months} month{'s' if months > 1 else ''}"


        industries    = ", ".join(exp_profile.get("primary_industries", []))
        skills        = ", ".join(exp_profile.get("top_skills", []))
        tools         = ", ".join(exp_profile.get("tools_and_equipment", []))
        
        raw_certs = exp_profile.get("certifications", [])
        if raw_certs and isinstance(raw_certs[0], dict):
            certs = ", ".join(c.get("certificate_name", "") for c in raw_certs if c.get("certificate_name"))
        else:
            certs = ", ".join(raw_certs)
        work_ethic    = fit_score.get("explanation", "")

        summary_prompt = PASSPORT_SUMMARY_PROMPT.format(
            years_experience = years_exp   or "Not specified",
            industries       = industries  or "General frontline work",
            skills           = skills      or "Not specified",
            tools            = tools       or "Not specified",
            certifications   = certs       or "None mentioned",
            work_ethic       = work_ethic  or "Not specified",
        )

        summary_response      = llm.invoke(summary_prompt)
        professional_summary  = summary_response.content.strip()
        state["professional_summary"] = professional_summary
        print(f"[PASSPORT] Professional summary: {professional_summary}")

        # Add to passport profile
        state["passport_profile"]["professional_summary"] = professional_summary

    except Exception as e:
        print(f"[PASSPORT] Summary generation error: {e}")
        professional_summary = ""
    # ─────────────────────────────────────────────────────────────────────────

    # ── Create candidate auth account ─────────────────────────────────────────
    auth_response = create_candidate_account(
        name    = name,
        email   = email,
        is_live = state.get("is_live", False),
    )
    # Extract onboard ID from response — share the log to confirm the exact key
    onboard_id   = auth_response.get("user", {}).get("id", "")
    passport_url = f"https://app.cleohr.com/onboard/{onboard_id}" if onboard_id else "https://app.cleohr.com/auth"
    print(f"[PASSPORT] Onboard URL: {passport_url}")
    # ─────────────────────────────────────────────────────────────────────────

    # ── Final PATCH ───────────────────────────────────────────────────────────
    update_passport_section(
        passport_id = state.get("passport_id", ""),
        section     = "final",
        data        = {
            "score":           int(fit_score.get("total_score", 0)),
            "passport_profile": state["passport_profile"],
        },
        is_live = state.get("is_live", False)
    )
    # ─────────────────────────────────────────────────────────────────────────

    wrap_w2 = (
        f"Here is the link to access your Candidate Passport: {passport_url}\n\n"
        "You can tap it anytime to view your verified skills dashboard, or copy and text it directly to hiring managers to apply on the spot!"
    )

    state["messages"].append(AIMessage(content=PASSPORT_WRAP_W1))
    state["messages"].append(AIMessage(content=wrap_w2))
    state["messages"].append(AIMessage(content=PASSPORT_WRAP_W3))

    return state


# ==================== GRAPH BUILDER ====================

def build_passport_graph(checkpointer):
    """Build the Cleo Work Passport LangGraph."""
    workflow = StateGraph(PassportState)

    # ── Nodes ─────────────────────────────────────────────────────────────────
    workflow.add_node("passport_greeting",          passport_greeting_node)
    workflow.add_node("store_privacy_consent",      store_privacy_consent_node)

    workflow.add_node("ask_name",                   ask_name_node)
    workflow.add_node("store_name",                 store_name_node)

    workflow.add_node("ask_knockout_question",      ask_knockout_question_node)
    workflow.add_node("store_kq_answer",            store_kq_answer_node)
    workflow.add_node("evaluate_single_knockout",   evaluate_single_knockout_node)

    workflow.add_node("ask_shift_preference",       ask_shift_preference_node)
    workflow.add_node("store_shift_preference",     store_shift_preference_node)

    workflow.add_node("ask_address",                ask_address_node)
    workflow.add_node("store_address",              store_address_node)

    workflow.add_node("ask_question",               ask_question_node)
    workflow.add_node("store_answer",               store_answer_node)

    workflow.add_node("ask_email",                  ask_email_node)
    workflow.add_node("store_email",                store_email_node)
    workflow.add_node("send_email_otp",             send_email_otp_node)
    workflow.add_node("ask_email_otp",              ask_email_otp_node)
    workflow.add_node("verify_email_otp",           verify_email_otp_node)

    workflow.add_node("ask_phone",                  ask_phone_node)
    workflow.add_node("store_phone",                store_phone_node)
    workflow.add_node("send_phone_otp",             send_phone_otp_node)
    workflow.add_node("ask_phone_otp",              ask_phone_otp_node)
    workflow.add_node("verify_phone_otp",           verify_phone_otp_node)

    # workflow.add_node("ask_work_experience",        ask_work_experience_node)
    workflow.add_node("store_work_experience_response", store_work_experience_response_node)

    workflow.add_node("ask_education",              ask_education_node)
    workflow.add_node("store_education",            store_education_node)

    workflow.add_node("ask_military",               ask_military_node)
    workflow.add_node("store_military",             store_military_node)

    workflow.add_node("ask_id_verification",        ask_id_verification_node)
    workflow.add_node("process_id_result",          process_id_result_node)

    workflow.add_node("passport_summary",           passport_summary_node)

    # ── Entry point ───────────────────────────────────────────────────────────
    workflow.set_entry_point("passport_greeting")

    # ── Edges ─────────────────────────────────────────────────────────────────

    # Greeting → privacy consent → name
    workflow.add_edge("passport_greeting", "store_privacy_consent")
    workflow.add_conditional_edges("store_privacy_consent", privacy_router)

    # Name
    workflow.add_edge("ask_name", "store_name")
    workflow.add_conditional_edges("store_name", name_router)

    # Knockout loop
    workflow.add_edge("ask_knockout_question", "store_kq_answer")
    workflow.add_edge("store_kq_answer", "evaluate_single_knockout")
    workflow.add_conditional_edges("evaluate_single_knockout", single_knockout_router)

    # Shift preference
    workflow.add_edge("ask_shift_preference", "store_shift_preference")
    workflow.add_conditional_edges("store_shift_preference", shift_router)

    # Address
    workflow.add_edge("ask_address", "store_address")
    workflow.add_edge("store_address", "ask_question")

    # Screening questions loop
    workflow.add_edge("ask_question", "store_answer")
    workflow.add_conditional_edges("store_answer", question_router)

    # Email flow
    workflow.add_edge("ask_email", "store_email")
    workflow.add_conditional_edges("store_email", email_router)
    workflow.add_conditional_edges("send_email_otp", email_otp_router)
    workflow.add_edge("ask_email_otp", "verify_email_otp")
    workflow.add_conditional_edges("verify_email_otp", email_otp_router)

    # Phone flow
    workflow.add_edge("ask_phone", "store_phone")
    workflow.add_conditional_edges("store_phone", phone_router)
    workflow.add_conditional_edges("send_phone_otp", phone_otp_router)
    workflow.add_edge("ask_phone_otp", "verify_phone_otp")
    workflow.add_conditional_edges("verify_phone_otp", phone_otp_router)

    # Work history
    # workflow.add_edge("ask_work_experience", "store_work_experience_response")
    workflow.add_edge("store_work_experience_response", "ask_education")

    # Education
    workflow.add_edge("ask_education", "store_education")
    workflow.add_edge("store_education", "ask_military")

    # Military
    workflow.add_edge("ask_military", "store_military")
    workflow.add_conditional_edges("store_military", military_router)

    # ID verification
    workflow.add_edge("ask_id_verification", "process_id_result")
    workflow.add_edge("process_id_result", "passport_summary")

    # End
    workflow.add_edge("passport_summary", END)

    # ── Compile with interrupts ───────────────────────────────────────────────
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=[
            "passport_greeting",
            "store_privacy_consent",
            "ask_knockout_question",
            "ask_shift_preference",
            "ask_address",
            "ask_question",
            "ask_email",
            "ask_email_otp",
            "ask_phone",
            "ask_phone_otp",
            "ask_id_verification",
            "store_work_experience_response",
            "ask_education",
            "ask_military",
        ]
    )

    return app