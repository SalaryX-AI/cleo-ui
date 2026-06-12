"""Main graph implementation for Cleo screening chatbot with human-in-the-loop"""
import asyncio
from datetime import datetime
import json
from typing import Literal, List, Dict
from urllib import response
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.types import interrupt
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from prompts1 import *
import os
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
import time
from xano import send_applicant_to_xano
from location_services import verify_location
import phonenumbers
from id_verification import create_id_verify_session, save_session_mapping
from conversation_logger import log_id_verification_event

from otp_verification import (
    generate_otp, 
    send_email_otp, 
    verify_otp,
    is_otp_expired,
    create_phone_verify_session,   
    validate_phone_otp,
)

from candidate_helpers import (
    extract_email_from_text,
    extract_phone_from_text,
    extract_age_from_text,
    generate_json_report
)

import cleo_engagement

# ========================================================
load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

evaluation_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# Create chat prompt template with system message
chat_template = ChatPromptTemplate.from_messages([
    ("system", SYSTEM_PROMPT),
    ("human", "{user_input}")
])

# ==================== Email & Phone Validation ====================
import re

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email.strip()))

def validate_phone(phone: str) -> bool:
    try:
        parsed = phonenumbers.parse(phone, None)
        return phonenumbers.is_valid_number(parsed)
    except:
        return False


GENERIC_AMBIGUITY_FAIL_MESSAGE = (
    "It looks like we've hit a small snag understanding that. "
    "If you'd like to try again, feel free to restart the chat whenever you're ready. Good luck!"
)

# ==================== State Definition ====================

class ChatbotState(MessagesState):
    """State for the screening chatbot"""
    current_question_index: int = 0
    questions: List[str] = []
    answers: Dict[str, str] = {}
    
    current_knockout_question_index: int = 0
    knockout_questions: List[str] = []
    knockout_answers: Dict[str, str] = {}
    knockout_passed: bool = False
    current_knockout_failed: bool = False
    
    scoring_model: Dict[str, Dict] = {}
    scores: Dict[str, float] = {}
    score: float = 0
    total_score: float = 0

    personal_details: Dict[str, str] = {}
    ready_confirmed: bool = False

    acknowledgement_type: str = ""
    delay_node_type: str = ""

    brand_name: str = ""

    # Validation tracking
    email_validation_failed: bool = False
    phone_validation_failed: bool = False
    invalid_email_attempt: str = ""
    invalid_phone_attempt: str = ""

    email_attempt_count: int = 0
    phone_attempt_count: int = 0

    # Email OTP fields
    email_otp_code: str = ""
    email_otp_sent: bool = False
    email_otp_sent_failed: bool = False
    email_otp_timestamp: float = 0
    email_verified: bool = False
    email_otp_attempts: int = 0
    
    # Phone OTP fields
    phone_otp_code: str = ""
    phone_otp_sent: bool = False
    phone_otp_sent_failed: bool = False
    phone_otp_timestamp: float = 0
    phone_verified: bool = False
    phone_otp_attempts: int = 0
    phone_verify_session_uuid: str = ""

    # ID Verification fields
    id_verify_link: str = ""
    id_verify_session_id: str = ""   # Simplici's session ID
    id_verified: bool = False
    id_verify_failed: bool = False
    show_id_verify_ui: bool = False

    session_id: str = ""
    job_id: str = ""
    company_id: str = ""
    is_live: bool = False

    applicant_age: str = ""

    # Add work experience tracking
    work_experience: List[Dict[str, str]] = []
    show_work_experience_ui: bool = False

    # Add education field
    education_level: str = ""
    show_education_ui: bool = False

    # Address fields
    address: Dict[str, str] = {}          # { street, city, state, zip, full }
    show_address_ui: bool = False

    # GPS verification fields
    gps_lat: float = 0.0
    gps_lng: float = 0.0
    gps_verified: bool = False
    gps_flagged: bool = False
    gps_flag_reason: str = ""
    gps_distance_miles: float = 0.0
    show_gps_ui: bool = False
    
    job_shift: str = ""
    job_type: str = ""

    # Certifications
    certifications: List[Dict[str, str]] = []   # [{"name": "ServSafe", "date": "2023"}]

    # Military service
    military_served: bool = False
    military_details: Dict[str, str] = {}       # {"branch": "", "duty": "", "rank": ""}
    military_follow_up_done: bool = False

    # Background check consent
    background_check_consented: bool = False

    referral_source: str = ""
    education_year: str = ""

    question_acknowledgements: Dict[str, str] = {}
    verification_required: str = ""

    experience_qualified: bool = True

    re_ask_attempts: Dict[str, int] = {}
    kq_just_answered_index: int = -1

    # Question evaluation fields
    required_questions: Dict[str, Dict] = {}
    flagged_questions: Dict[str, Dict] = {}
    required_question_failed: bool = False
    manager_flags: List[str] = []
    phone_hard_stop: bool = False
    kq_ambiguous_default: bool = False
    generic_fail: bool = False
    email_hard_stop: bool = False
    single_company: bool = False
    incomplete_application: bool = False


# ===========================================================================================================
def generate_reask_message(question: str, user_input: str) -> str:
    """LLM-generated conversational re-ask that acknowledges what the user said"""
    prompt = f"""You are Cleo, a friendly AI hiring assistant. A job applicant gave an unclear response.

Question asked: "{question}"
Applicant's response: "{user_input}"

Write a brief, warm, conversational follow-up (1 sentence) that:
- Naturally acknowledges what they said
- Gently re-asks for what you need and why
- Does NOT sound robotic or use phrases like "I didn't catch that"
- Feels like a real conversation and should be professional and empathize but not too formal.
- Use simple language, no jargon with exact question

Return ONLY the message, nothing else."""
    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        return response.content.strip()
    except Exception:
        return f"Just to confirm — {question}"
    


def interpret_response(question: str, answer: str, expected_type: str = "yes_no") -> dict:
    """
    Central response interpreter. Never stores raw input — always returns meaning.
    
    Returns:
        {"intent": "yes"|"no"|"ambiguous", "clean": "normalized value", "reason": "if ambiguous"}
    """
    if expected_type == "free_text":
        return {"intent": "value", "clean": answer.strip(), "reason": ""}

    prompt = f"""You are interpreting a job applicant's chat response.

Question: "{question}"
Response: "{answer}"

Classify the response as YES, NO, or AMBIGUOUS.

YES examples: yes, y, yep, yup, yeah, sure, of course, absolutely, definitely, 
              correct, i do, i am, i have, i can, for sure, totally, certainly, 
              "i served" (military), "i have experience", "i'm available", "sounds good"

NO examples: no, n, nope, nah, not really, i don't, i can't, i haven't, i'm not, 
             negative, never, "no experience", "can't make it"

AMBIGUOUS — use this when:
- Gibberish or typos with no clear meaning: "yrdy", "yryd", "asd", "lkj", random characters
- Too vague: "maybe", "depends", "sometimes", "i think so", "probably", "not sure"
- Unrelated to the question
- Single letters other than y or n

Return ONLY valid JSON, no markdown:
{{"intent": "yes" or "no" or "ambiguous", "clean": "yes or no or the original text", "reason": "brief reason if ambiguous, otherwise empty string"}}"""

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        clean = response.content.strip().replace("```json","").replace("```","").strip()
        result = json.loads(clean)
        return result
    except Exception:
        lower = answer.strip().lower()
        if lower in ("yes","y","yep","yeah","yup","sure","ok","okay"):
            return {"intent": "yes", "clean": "yes", "reason": ""}
        elif lower in ("no","n","nope","nah"):
            return {"intent": "no", "clean": "no", "reason": ""}
        return {"intent": "ambiguous", "clean": answer, "reason": "Could not interpret"}


# ==================== Acknowledgement ====================
def acknowledge_node(state: ChatbotState) -> ChatbotState:
    """Send acknowledgment message"""
    print(f"acknowledge_node called (type: {state['acknowledgement_type']})")

    ack_type = state.get("acknowledgement_type", "default")

    ack_messages = cleo_engagement.ack_messages
    
    message = ack_messages.get(ack_type) or ack_messages.get("default", "Let's continue!")

    state["messages"].append(AIMessage(content=message))
    
    return state

def post_acknowledgement_router(state: ChatbotState) -> Literal["ask_knockout_question", "ask_work_experience", "ask_id_verification"]:
    """Decide where to go after acknowledgement"""
    
    # If we're done with personal details, go to ID verification
    # if state.get("acknowledgement_type") == "questions" and state.get("job_type") == "server":
    #     print("Routing to ask_work_experience due to server role after questions acknowledgement")
    #     return "ask_work_experience"
    
    if state.get("acknowledgement_type") == "questions":
        print("Routing to ask_id_verification due to questions acknowledgement")
        return "ask_work_experience"
    
    # Otherwise, start knockout questions
    return "ask_knockout_question"


# ==================== Delay messages ====================

def delay_messages_node(state: ChatbotState) -> ChatbotState:
    """Node that adds delayed messages"""
    
    print(f"delay_messages_node called (type: {state['delay_node_type']})")

    message_map = {
        "greeting": [
            f"Our employees are the heart of {state.get('brand_name')} — a five-star senior living community in Boca Raton.",
            "I just need to ask a few quick screening questions, it should only take a couple of minutes. Ready to start? (You can type 'Stop' anytime.)"
        ],
        "end": [
            "Our hiring team is now reviewing your profile. If your experience is a match, we'll reach out via email or phone to discuss the next steps.",
            f"You can expect to hear from us within 1 business day. Thank you again for your time and interest in working with {state.get('brand_name')}!",
            "Good Bye! 👋"
        ],
            "default": "Let's continue!"
    }
    
    delay_node_type = state.get("delay_node_type", "default")
    messages = message_map.get(delay_node_type)
    
    # Handle list or single message
    if isinstance(messages, list):
        for msg in messages:
            state["messages"].append(AIMessage(content=msg))
    else:
        state["messages"].append(AIMessage(content=messages))
    
    return state

def post_delay_router(state: ChatbotState) -> Literal["check_ready", "__end__"]:
    """Decide where to go after delay messages"""
    
    # If we're done with personal details, start questions
    if state.get("delay_node_type") == "greeting":
        return "check_ready"
    
    # Otherwise, start knockout questions
    return "__end__"


# ==================== START & READY FLOW ====================

def start_node(state: ChatbotState) -> ChatbotState:
    """Send greeting"""

    print("start_node called")

    state["messages"].append(AIMessage(content=f"Hello! I'm Cleo, the hiring assistant for {state['brand_name']}.Thank you for your interest."))

    state["delay_node_type"] = "greeting"
    
    return state


def check_ready_node(state: ChatbotState) -> ChatbotState:
    print("check_ready_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.lower().strip()
        question = "Are you ready to start the application process?"

        result = interpret_response(question, user_input, "yes_no")

        if result["intent"] == "ambiguous":
            attempts = state["re_ask_attempts"].get("ready", 0) + 1
            state["re_ask_attempts"]["ready"] = attempts

            if attempts >= 3:
                # Default to decline after 3 unclear responses
                state["ready_confirmed"] = False
                state["messages"].append(AIMessage(content=cleo_engagement.decline_message))
                state["re_ask_attempts"].pop("ready", None)
            else:
                reask = generate_reask_message(question, user_input)
                state["messages"].append(AIMessage(content=reask))

        elif result["intent"] == "yes":
            state["ready_confirmed"] = True
            state["re_ask_attempts"].pop("ready", None)

        else:
            state["ready_confirmed"] = False
            state["messages"].append(AIMessage(content=cleo_engagement.decline_message))
            state["re_ask_attempts"].pop("ready", None)

    return state


def reask_consent_node(state: ChatbotState) -> ChatbotState:
    """Pure interrupt point after ambiguous consent — message already sent by check_ready_node"""
    return {}


def ready_router(state: ChatbotState) -> Literal["ask_knockout_question", "reask_consent", "__end__"]:
    print("ready_router called")

    if "ready" in state.get("re_ask_attempts", {}):
        return "reask_consent"

    if state["ready_confirmed"]:
        return "ask_knockout_question"

    return "__end__"

# ==================== knockout questions ============================
def ask_knockout_question_node(state: ChatbotState) -> ChatbotState:
    """Ask knockout questions"""

    print("ask_knockout_question_node called")

    idx = state["current_knockout_question_index"]
    knockout_questions = state["knockout_questions"]

    if idx < len(knockout_questions):
        knockout_question = knockout_questions[idx]

        # ── Re-ask — generate dynamic conversational message ─────────────────
        if knockout_question in state.get("re_ask_attempts", {}):
            last_human = next(
                (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
                None
            )
            user_input = last_human.content if last_human else ""
            reask = generate_reask_message(knockout_question, user_input)
            state["messages"].append(AIMessage(content=reask))
            return state

        # ── Initial ask ───────────────────────────────────────────────────────
        if idx == 2:
            raw_shift = state.get('job_shift', '').strip()
            if raw_shift:
                shifts_text = raw_shift.replace(", and ", ",\n").replace(", ", ",\n")
                content = f"We are currently hiring specifically for:\n{shifts_text}.\nAre you available to work that schedule?"
            else:
                content = "Are you available to work various shifts including mornings, evenings, and weekends?"
            state["messages"].append(AIMessage(content=content))
        else:
            state["messages"].append(AIMessage(content=knockout_question))

    return state
    


def store_kq_answer_node(state: ChatbotState) -> ChatbotState:
    print("store_kq_answer_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    idx = state["current_knockout_question_index"]
    if idx >= len(state["knockout_questions"]):
        return state

    knockout_question = state["knockout_questions"][idx]

    # ── Age question (idx==1) ─────────────────────────────────────────────────
    if idx == 1:
        user_input = last_message.content.strip()

        # ── Step 1: Check for clear yes/no intent first ───────────────────────
        intent_check = interpret_response(knockout_question, user_input, "yes_no")

        if intent_check["intent"] == "no":
            # Clear negative — store directly, skip age extraction
            print(f"[KQ-AGE] Clear NO detected → storing no")
            state["knockout_answers"][knockout_question] = "no"
            state["applicant_age"] = "NONE"
            state["current_knockout_question_index"] += 1
            state["re_ask_attempts"].pop(knockout_question, None)
            state["kq_just_answered_index"] = idx
            return state

        # ── Step 2: Bare number pre-check ────────────────────────────────────
        if re.fullmatch(r'\d+', user_input):
            age_int = int(user_input)
            age = str(age_int) if 0 < age_int < 120 else "NONE"
            print(f"[KQ-AGE] Bare number detected: {age}")
        else:
            age = extract_age_from_text(user_input)

        print(f"Extracted age: {age}")

        # ── Step 3: NONE = ambiguous ──────────────────────────────────────────
        if age == "NONE":
            attempts = state["re_ask_attempts"].get(knockout_question, 0) + 1
            state["re_ask_attempts"][knockout_question] = attempts
            print(f"[KQ-AGE] Could not extract age, attempt {attempts}")

            if attempts >= 3:
                state["knockout_answers"][knockout_question] = "no"
                state["applicant_age"] = "NONE"
                state["re_ask_attempts"].pop(knockout_question, None)
                state["kq_just_answered_index"] = idx
                state["kq_ambiguous_default"] = True  
            else:
                state["kq_just_answered_index"] = -1
            return state

        # ── Step 4: Valid age — normalize to yes/no ───────────────────────────
        state["applicant_age"] = age
        try:
            age_num = float(re.sub(r'[^\d.]', '', age))
            state["knockout_answers"][knockout_question] = "yes" if age_num >= 18 else "no"
            print(f"[KQ-AGE] {age} → {'yes' if age_num >= 18 else 'no'}")
        except Exception:
            state["knockout_answers"][knockout_question] = age

        state["current_knockout_question_index"] += 1
        state["re_ask_attempts"].pop(knockout_question, None)
        state["kq_just_answered_index"] = idx
        return state

    # ── All other KQ: yes/no with ambiguity detection ─────────────────────────
    result = interpret_response(knockout_question, last_message.content, "yes_no")
    print(f"KQ interpret result: {result}")

    if result["intent"] == "ambiguous":
        attempts = state["re_ask_attempts"].get(knockout_question, 0) + 1
        state["re_ask_attempts"][knockout_question] = attempts

        if attempts >= 3:
            print(f"[KQ] 3 ambiguous attempts — defaulting to no")
            state["knockout_answers"][knockout_question] = "no"
            state["re_ask_attempts"].pop(knockout_question, None)
            state["kq_just_answered_index"] = idx     
            state["kq_ambiguous_default"] = True      
        else:
            state["kq_just_answered_index"] = -1           
        return state

    # Clear answer
    state["knockout_answers"][knockout_question] = result["clean"]
    state["current_knockout_question_index"] += 1
    state["re_ask_attempts"].pop(knockout_question, None)
    state["kq_just_answered_index"] = idx                  # ← mark as answered
    return state


def kq_ambiguity_router(state: ChatbotState) -> Literal["ask_knockout_question", "evaluate_single_knockout"]:
    if state.get("kq_just_answered_index", -1) >= 0:
        return "evaluate_single_knockout"
    return "ask_knockout_question"

# ==================== KNOCKOUT EVALUATION (Per Question) ====================

def evaluate_single_knockout_node(state: ChatbotState) -> ChatbotState:
    """Evaluate the most recent knockout answer"""
    
    print("evaluate_single_knockout_node called")
    
    knockout_questions = state["knockout_questions"]
    knockout_answers = state["knockout_answers"]

    just_answered = state.get("kq_just_answered_index", -1)
    if just_answered >= 0:
        current_index = just_answered
    else:
        current_index = state["current_knockout_question_index"] - 1
    if current_index < 0 or current_index >= len(knockout_questions):
        return state
    
    current_question = knockout_questions[current_index]
    current_answer = knockout_answers.get(current_question, "No answer")
    
    print(f"Evaluating Q{current_index + 1}: {current_question}")
    print(f"Answer: {current_answer}")
    print(f"Answer repr: {repr(current_answer)}")
    print(f"Answer length: {len(current_answer)}")
    
    normalized_answer = current_answer.strip()
    
    print(f"After strip: {repr(normalized_answer)}")
    print(f"Upper: {repr(normalized_answer.upper())}")

    if normalized_answer.upper() == "Y":
        normalized_answer = "yes"
        decision = "YES"
        print(f"[NORMALIZED] 'Y' → 'yes', Decision: YES")
    elif normalized_answer.upper() == "N":
        normalized_answer = "no"
        decision = "NO"
        print(f"[NORMALIZED] 'N' → 'no', Decision: NO")
    else:
        print(f"[NOT NORMALIZED] Sending to LLM: {repr(normalized_answer)}")
        
        prompt = f"""
        Evaluate if this answer is positive (YES) or negative (NO).
        
        Question: {current_question}
        Answer: "{normalized_answer}"
        
        Rules for YES:
        - Full words: "yes", "yeah", "yep", "yup", "sure", "okay", "ok", "definitely", "of course", "absolutely"
        - Phrases: "I am", "I have", "I can", "I do", "available"
        - For age questions: any number ≥18
        
        Rules for NO:
        - Full words: "no", "nope", "not", "don't", "can't", "unavailable"
        - For age questions: any number <18
        
        Return ONLY "YES" or "NO". Nothing else.
        
        Decision:
        """
        
        response = evaluation_llm.invoke(prompt)
        decision = response.content.strip().upper()
        print(f"LLM Decision: {decision}")

    print(f"Final Decision: {decision}")
    
    if decision == "NO":
        state["current_knockout_failed"] = True

        # Clear NO answer — direct failure messages
        failure_messages = [
            "We are only allowed to hire applicants who are legally eligible to work in the U.S. Thank you for your time!",
            "The minimum age for this position is 18. Thank you for your time!",
            "I see. We can continue the application process and the hiring manager will review to see if there may be another position available that fits your availability.",
            "I see. Reliable transportation is crucial for this position. Unfortunately, this is a requirement for the role. Thank you so much for taking the time to chat with me today!"
        ]

        # Ambiguous after 3 attempts — softer phrasing
        ambiguous_failure_messages = [
            "We can only move forward with applicants eligible to work in the U.S. Thank you for your time!",
            "This role requires you to be at least 18. Thank you for your time!",
            "We only have evening and weekend openings right now. Thank you for your time!",
            "Reliable transportation is required for this role. Thank you for your time!"
        ]

        messages_list = ambiguous_failure_messages if state.get("kq_ambiguous_default") else failure_messages
        failure_message = messages_list[current_index] if current_index < len(messages_list) else messages_list[-1]

        state["kq_ambiguous_default"] = False   # reset flag
        state["messages"].append(AIMessage(content=failure_message))
    
    else:
        state["current_knockout_failed"] = False
        
        acknowledgment_messages = [
            "Got it, thank you.",
            "Great.",
            "Perfect! That sounds like a good fit for our team.",
            ""
        ]
        
        ack_message = acknowledgment_messages[current_index] if current_index < len(acknowledgment_messages) else ""
        
        if ack_message:
            state["messages"].append(AIMessage(content=ack_message))
    
    return state

def single_knockout_router(state: ChatbotState) -> Literal["ask_knockout_question", "ask_question", "__end__"]:
    """Route based on single knockout evaluation"""
    
    print("single_knockout_router called")
    
    # Check if current question failed
    if state.get("current_knockout_failed", False):
        return "__end__"  # End conversation
    
    # Check if more questions remain
    if state["current_knockout_question_index"] < len(state["knockout_questions"]):
        return "ask_knockout_question"  # Ask next question
    
    # All KQs passed — skip screening questions if none configured
    if not state.get("questions"):
        return "ask_address" 
    
    # All questions passed
    return "ask_question"  # Continue to work experience


# ==================== QUESTIONS LOOP ====================
def ask_question_node(state: ChatbotState) -> ChatbotState:
    """Ask screening question"""
    
    print("ask_question_node called")

    questions = state["questions"] or []

    # No screening questions configured — skip silently
    if not questions:
        return {}
    
    idx = state["current_question_index"]
    
    if idx < len(questions):
        question = questions[idx]    

        if question in state.get("re_ask_attempts", {}):
            return {}    
        
        state["messages"].append(AIMessage(content=question))
    
    return state


def store_answer_node(state: ChatbotState) -> ChatbotState:
    print("store_answer_node called")
    print(f"Current question index: {state['current_question_index']}")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    idx = state["current_question_index"]
    if idx >= len(state["questions"]):
        return state

    question = state["questions"][idx]

    # ── Interpret response ────────────────────────────────────────────────────
    result = interpret_response(question, last_message.content, "yes_no")
    print(f"Answer interpret result: {result}")

    # ── Ambiguous path ────────────────────────────────────────────────────────
    if result["intent"] == "ambiguous":
        attempts = state["re_ask_attempts"].get(question, 0) + 1
        state["re_ask_attempts"][question] = attempts

        if attempts >= 3:
            print(f"[ANSWER] 3 ambiguous attempts — ending")
            state["current_question_index"] += 1
            state["re_ask_attempts"].pop(question, None)

            # Required question → specific fail message + end
            required_questions = state.get("required_questions", {})
            if question in required_questions:
                state["messages"].append(AIMessage(
                    content=required_questions[question]["fail_message"]
                ))
                state["required_question_failed"] = True
                return state

            # Flagged question → flag silently + generic end
            flagged_questions = state.get("flagged_questions", {})
            if question in flagged_questions:
                flags = list(state.get("manager_flags", []))
                flags.append(flagged_questions[question]["flag_reason"])
                state["manager_flags"] = flags
                print(f"[FLAG] Manager flag added: {flagged_questions[question]['flag_reason']}")

            # All others (including flagged) → generic end
            state["messages"].append(AIMessage(content=GENERIC_AMBIGUITY_FAIL_MESSAGE))
            state["generic_fail"] = True
            return state

        else:                                                              # ← fix: was missing
            reask = generate_reask_message(question, last_message.content)
            state["messages"].append(AIMessage(content=reask))
        return state                                                       # ← fix: was missing

    # ── Clear answer — normalize to yes/no ───────────────────────────────────
    if result["intent"] == "yes":
        state["answers"][question] = "yes"
    elif result["intent"] == "no":
        state["answers"][question] = "no"
    else:
        state["answers"][question] = result["clean"]

    state["current_question_index"] += 1
    state["re_ask_attempts"].pop(question, None)

    # ── Experience check question (hard stop on NO) ───────────────────────────
    exp_question = state.get("experience_check_question", "")
    if exp_question and question == exp_question:
        qualified = result["intent"] == "yes"
        state["experience_qualified"] = qualified
        print(f"Experience qualified: {qualified}")

        if qualified:
            ack = state.get("question_acknowledgements", {}).get(question, "")
            if ack:
                state["messages"].append(AIMessage(content=ack))
        else:
            state["messages"].append(AIMessage(
                content=state.get("experience_fail_message", "Thank you for your time!")
            ))
        return state

    # ── Required question (pass ack or fail + end) ────────────────────────────
    required_questions = state.get("required_questions", {})
    if question in required_questions:
        req = required_questions[question]
        if result["intent"] == "yes":
            state["messages"].append(AIMessage(content=req["pass_ack"]))
        else:
            state["messages"].append(AIMessage(content=req["fail_message"]))
            state["required_question_failed"] = True
        return state

    # ── Flagged question (pass ack or flag + optional no_response) ────────────
    flagged_questions = state.get("flagged_questions", {})
    if question in flagged_questions:
        fq = flagged_questions[question]
        if result["intent"] == "yes":
            state["messages"].append(AIMessage(content=fq["pass_ack"]))
        else:
            flags = list(state.get("manager_flags", []))
            flags.append(fq["flag_reason"])
            state["manager_flags"] = flags
            print(f"[FLAG] Manager flag added: {fq['flag_reason']}")
            no_resp = fq.get("no_response", "")
            if no_resp:
                state["messages"].append(AIMessage(content=no_resp))
        return state

    # ── Regular question (acknowledgement only) ───────────────────────────────
    ack = state.get("question_acknowledgements", {}).get(question, "")
    if ack:
        state["messages"].append(AIMessage(content=ack))

    return state


def experience_router(state: ChatbotState) -> Literal["ask_question", "__end__", "ask_address"]:
    print("experience_router called")
    
    if not state.get("experience_qualified", True):
        return "__end__"
    
    # Check if more questions remain
    idx       = state["current_question_index"]
    questions = state.get("questions", [])

    if idx < len(questions):
        return "ask_question"
    
    return "ask_address"


def answer_router(state: ChatbotState) -> Literal["ask_question", "ask_address", "__end__"]:
    print("answer_router called")

    if state.get("required_question_failed"):
        return "__end__"

    if state.get("generic_fail"):
        return "__end__"

    if not state.get("experience_qualified", True):
        return "__end__"

    idx       = state["current_question_index"]
    questions = state.get("questions", [])

    # No screening questions — skip to next section
    if not questions:
        return "ask_address"

    if idx < len(questions) and questions[idx] in state.get("re_ask_attempts", {}):
        return "ask_question"

    if idx < len(questions):
        return "ask_question"

    return "ask_address"

# ================================= ADDRESS =========================================

def ask_address_node(state: ChatbotState) -> ChatbotState:
    """Ask for home address and show autocomplete UI"""

    print("ask_address_node called")

    state["messages"].append(AIMessage(
        content="Perfect. Since this role is on-site, could you please share your home address? We just want to make sure the commute will be manageable for you!"
    ))
    state["show_address_ui"] = True   # Signal frontend to show autocomplete UI

    return state


def store_address_node(state: ChatbotState) -> ChatbotState:
    """Store structured address received from frontend"""

    print("store_address_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        # Address data arrives as JSON string: '{"street":...,"city":...}'
        try:
            import json as _json
            address_data = _json.loads(last_message.content)
            state["address"] = address_data
            print(f"Stored address: {address_data}")
        except Exception:
            # Fallback: plain text address
            state["address"] = {"full": last_message.content}
            print(f"Stored plain address: {last_message.content}")

    return state


def ask_gps_verification_node(state: ChatbotState) -> ChatbotState:
    """Ask user to share GPS location"""

    print("ask_gps_verification_node called")

    state["messages"].append(AIMessage(
        content="Thanks! Just to wrap up the local residency check, could you share your current GPS location? This helps us confirm you're within a comfortable driving distance."
    ))
    state["show_gps_ui"] = True   # Signal frontend to show GPS button

    return state


def process_gps_node(state: ChatbotState) -> ChatbotState:
    """Receive GPS coordinates and cross-verify against typed address"""

    print("process_gps_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        try:
            import json as _json
            gps_data = _json.loads(last_message.content)
            
            lat = gps_data.get("lat")
            lng = gps_data.get("lng")
            skipped = gps_data.get("skipped", False)

            # Handle skip case immediately
            if skipped or lat is None or lng is None:
                state["gps_verified"] = False
                state["gps_flagged"] = False
                state["messages"].append(AIMessage(
                    content="No problem! We'll proceed with the address you provided."
                ))
                return state

            # convert now
            lat = float(lat)
            lng = float(lng)

            state["gps_lat"] = lat
            state["gps_lng"] = lng

            typed_address = state.get("address", {}).get("full", "")

            if typed_address and lat and lng:
                result = verify_location(typed_address, lat, lng)

                state["gps_verified"] = result["verified"]
                state["gps_flagged"] = result["flag"]
                state["gps_flag_reason"] = result.get("flag_reason", "")
                state["gps_distance_miles"] = result.get("distance_miles", 0.0)

                print(f"GPS verification result: {result}")

                if result["flag"]:
                    # Soft flag - ask clarifying question, don't hard-stop
                    state["gps_flagged"] = True
                    state["gps_flag_reason"] = result.get("flag_reason", "")
                    
                    # state["messages"].append(AIMessage(
                    #     content=f"Thanks for sharing! We noticed your current location appears to be about {result['distance_miles']:.1f} mile(s) from the address you provided. Can you confirm that {typed_address} is your correct home address?"
                    # ))
                else:
                    state["messages"].append(AIMessage(
                        content="Verified! ✅ You're definitely within range."
                    ))
            else:
                # No address to compare, just accept GPS
                state["gps_verified"] = False
                state["messages"].append(AIMessage(
                    content="GPS Location received, We'll proceed with this"
                ))

        except Exception as e:
            print(f"GPS processing error: {e}")
            # GPS failed gracefully - don't block flow
            state["gps_verified"] = False
            state["gps_flagged"] = False
            state["gps_flag_reason"] = "GPS data could not be processed"

    return state


def gps_router(state: ChatbotState) -> Literal["ask_name"]:
    """
    Route after GPS processing.
    Flagged addresses get a soft clarifying question but still continue.
    This is never a hard stop - just flags for manual review.
    """
    print("gps_router called")
    # Always continue to questions regardless of flag
    # Flag is stored in state for XANO/hiring manager review
    return "ask_name"


# ==================== PERSONAL DETAILS COLLECTION ====================

def ask_name_node(state: ChatbotState) -> ChatbotState:
    print("ask_name_node called")

    attempts = state.get("re_ask_attempts", {}).get("name", 0)

    if attempts > 0:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        reask = generate_reask_message(
            "What is your first and last name?", user_input
        )
        state["messages"].append(AIMessage(content=reask))
    else:
        state["messages"].append(AIMessage(content=cleo_engagement.ask_name))

    return state


def store_name_node(state: ChatbotState) -> ChatbotState:
    print("store_name_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()

    prompt = f"""Is this a valid full name (first name + last name)?

Input: "{user_input}"

Rules for VALID:
- Has at least two separate words
- Contains only letters, spaces, hyphens, or apostrophes
- Is NOT gibberish or random characters

Return ONLY "YES" or "NO". Nothing else."""

    response = evaluation_llm.invoke(prompt)
    is_valid = response.content.strip().upper() == "YES"

    if not is_valid:
        attempts = state["re_ask_attempts"].get("name", 0) + 1
        state["re_ask_attempts"]["name"] = attempts
        print(f"[NAME] Invalid name, attempt {attempts}: {user_input}")

        if attempts >= 3:
            print(f"[NAME] 3 attempts — ending conversation")
            state["re_ask_attempts"].pop("name", None)
            state["messages"].append(AIMessage(content=GENERIC_AMBIGUITY_FAIL_MESSAGE))
            state["generic_fail"] = True
        return state

    print(f"[NAME] Valid name: {user_input}")
    state["personal_details"]["name"] = user_input
    state["re_ask_attempts"].pop("name", None)
    return state

def name_router(state: ChatbotState) -> Literal["ask_name", "ask_email", "__end__"]:
    if state.get("generic_fail"):
        return "__end__"
    if "name" not in state.get("personal_details", {}):
        return "ask_name"
    return "ask_email"


# ==================== EMAIL COLLECTION ====================
def ask_email_node(state: ChatbotState) -> ChatbotState:
    print("ask_email_node called")

    # Refusal re-ask — message already sent by store_email_node
    if "email_refusal" in state.get("re_ask_attempts", {}):
        return {}

    # Invalid format re-ask
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
        if state.get("email_otp_sent_failed") == True:
            state["messages"].append(AIMessage(
                content="Kindly enter your email address again (example: john.doe@example.com)"
            ))
            state["email_otp_sent_failed"] = False
            return state

        prompt = PERSONAL_DETAIL_ASK_PROMPT.format(
            detail_type="email",
            previous_question="What is your full name?",
            previous_answer=state["personal_details"].get("name", "None")
        )

    messages = chat_template.format_messages(user_input=prompt)
    response = llm.invoke(messages)
    state["messages"].append(AIMessage(content=response.content))
    return state


def store_email_node(state: ChatbotState) -> ChatbotState:
    """Store email with refusal detection + validation"""

    print("store_email_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_text = last_message.content.strip()
    print(f"Original input: {user_text}")

    # ── Refusal detection ─────────────────────────────────────────────────────
    refusal_attempts = state.get("re_ask_attempts", {}).get("email_refusal", 0)
    result = interpret_response("Can you provide your email address?", user_text, "yes_no")
    print(f"[EMAIL] Intent: {result['intent']}")

    if result["intent"] == "no":
        attempts = refusal_attempts + 1
        state["re_ask_attempts"]["email_refusal"] = attempts
        print(f"[EMAIL] Refusal detected, attempt {attempts}")

        if attempts >= 2:
            state["email_hard_stop"] = True
            state["re_ask_attempts"].pop("email_refusal", None)
            state["messages"].append(AIMessage(
                content="No problem at all! Since an email address is required to complete your application, we'll need to pause here. Thank you so much for your time! 🙏"
            ))
        else:
            state["messages"].append(AIMessage(
                content="An email address is required to keep you updated on your application and send interview details. Could you please share it? (e.g. john.doe@example.com)"
            ))
        return state

    # ── Normal extraction path ────────────────────────────────────────────────
    state["re_ask_attempts"].pop("email_refusal", None)

    email = extract_email_from_text(user_text)
    print(f"Extracted email: {email}")

    if validate_email(email):
        state["personal_details"]["email"] = email
        state["email_validation_failed"] = False
        state["invalid_email_attempt"] = ""
        state["email_attempt_count"] = 0
        print("Valid email stored:", email)
    else:
        count = state.get("email_attempt_count", 0) + 1
        state["email_attempt_count"] = count
        state["email_validation_failed"] = True
        state["invalid_email_attempt"] = email
        print("Invalid email detected:", email)

        if count >= 3:
            state["messages"].append(AIMessage(content=GENERIC_AMBIGUITY_FAIL_MESSAGE))
            state["email_hard_stop"] = True

    return state

def email_router(state: ChatbotState) -> Literal["ask_email", "send_email_otp", "__end__"]:
    print("email_router called")

    # Hard stop — refused twice or too many invalid attempts
    if state.get("email_hard_stop"):
        return "__end__"

    # Refusal attempt 1 — re-ask (message already sent)
    if "email_refusal" in state.get("re_ask_attempts", {}):
        return "ask_email"

    # Invalid format — re-ask
    if state.get("email_validation_failed"):
        return "ask_email"

    return "send_email_otp"


# ==================== PHONE COLLECTION ====================

def ask_phone_node(state: ChatbotState) -> ChatbotState:
    print("ask_phone_node called")

    # Refusal or invalid — message already sent by store_phone_node
    if "phone_refusal" in state.get("re_ask_attempts", {}) or state.get("phone_validation_failed"):
        return {}

    # First time — show full consent message
    state["messages"].append(AIMessage(content=cleo_engagement.ask_phone))
    return state


def store_phone_node(state: ChatbotState) -> ChatbotState:
    """Store phone with single LLM call for classification + response generation"""

    print("store_phone_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_text = last_message.content.strip()
    print(f"Original input: {user_text}")

    refusal_attempts = state.get("re_ask_attempts", {}).get("phone_refusal", 0)

    # ── Single LLM call: classify + extract + generate response ──────────────
    prompt = PHONE_ANALYSIS_PROMPT.format(
        user_input=user_text,
        attempt_count=refusal_attempts + 1
    )

    try:
        import json as _json
        resp = llm.invoke([HumanMessage(content=prompt)])
        clean = resp.content.strip().replace("```json", "").replace("```", "").strip()
        result = _json.loads(clean)
    except Exception as e:
        print(f"[PHONE] LLM parse error: {e}")
        result = {
            "intent": "invalid",
            "phone": None,
            "message": "I didn't catch that — could you share your phone number? (e.g. +1 555 123 4567)"
        }

    intent  = result.get("intent", "invalid")
    phone   = result.get("phone")
    message = result.get("message")

    print(f"[PHONE] Intent: {intent}, Phone: {phone}")

    # ── Refusal ───────────────────────────────────────────────────────────────
    if intent == "refusal":
        attempts = refusal_attempts + 1
        state["re_ask_attempts"]["phone_refusal"] = attempts

        if attempts >= 2:
            state["phone_hard_stop"] = True
            state["phone_validation_failed"] = True
            state["re_ask_attempts"].pop("phone_refusal", None)
            # Fixed closing message — don't use LLM here, it contradicts the hard stop
            state["messages"].append(AIMessage(
                content="No problem at all! Since a phone number is required to complete the application, we'll need to pause here. Thank you so much for your time — we hope to connect with you again in the future! 🙏"
            ))
        else:
            # LLM-generated warm message for attempt 1 only
            state["messages"].append(AIMessage(content=message))

        return state

    # ── Invalid / gibberish ───────────────────────────────────────────────────
    if intent == "invalid":
        count = state.get("phone_attempt_count", 0) + 1
        state["phone_attempt_count"] = count
        state["phone_validation_failed"] = True
        state["invalid_phone_attempt"] = user_text

        if count >= 3:
            state["messages"].append(AIMessage(
                content="It seems we're having trouble with the phone number. Unfortunately we need a valid number to proceed. Thank you for your time! 🙏"
            ))
        else:
            state["messages"].append(AIMessage(content=message))
        return state

    # ── Provided — validate the extracted number ──────────────────────────────
    state["re_ask_attempts"].pop("phone_refusal", None)

    if phone and validate_phone(phone):
        print(f"[PHONE] Valid: {phone}")
        state["personal_details"]["phone"] = phone
        state["phone_validation_failed"] = False
        state["invalid_phone_attempt"] = ""
        state["phone_attempt_count"] = 0
        state["acknowledgement_type"] = "questions"
    else:
        print(f"[PHONE] Provided but failed validation: {phone}")
        count = state.get("phone_attempt_count", 0) + 1
        state["phone_attempt_count"] = count
        state["phone_validation_failed"] = True
        state["invalid_phone_attempt"] = phone or user_text

        if count >= 3:
            state["messages"].append(AIMessage(
                content="It seems we're having trouble with your phone number. Unfortunately we need a valid number to proceed. Thank you for your time! 🙏"
            ))
        else:
            state["messages"].append(AIMessage(
                content="I wasn't able to recognize that as a valid number. Could you double-check and try again? (e.g. +1 555 123 4567)"
            ))

    return state


def phone_router(state: ChatbotState) -> Literal["ask_phone", "send_phone_otp", "__end__"]:
    print("phone_router called")

    # Hard stop — refused twice
    if state.get("phone_hard_stop"):
        return "__end__"

    # Hard stop — too many invalid attempts
    if state.get("phone_attempt_count", 0) >= 3:
        return "__end__"

    # Refusal attempt 1 — re-ask (message already sent)
    if "phone_refusal" in state.get("re_ask_attempts", {}):
        return "ask_phone"

    # Invalid format or gibberish — re-ask
    if state.get("phone_validation_failed", False):
        return "ask_phone"

    # Valid phone stored — continue
    return "send_phone_otp"


# ==================== EMAIL OTP VERIFICATION NODES ====================

def send_email_otp_node(state: ChatbotState) -> ChatbotState:
    """Generate and send OTP to email"""
    
    print("send_email_otp_node called")

    # ── Reset stale OTP state ─────────────────────────────────────────────────
    state["email_otp_sent_failed"] = False
    state["email_otp_attempts"]    = 0
    # ─────────────────────────────────────────────────────────────────────────
    
    email = state["personal_details"].get("email", "")
    user_name = state["personal_details"].get("name")
    
    # Generate OTP
    # otp_code = generate_otp()
    otp_code = "444444"  # For testing
    
    # Store in state
    state["email_otp_code"] = otp_code
    state["email_otp_timestamp"] = time.time()
    brand_name = state.get("brand_name")
    
    # Send email
    # success = send_email_otp(email, otp_code, brand_name, user_name)
    success = True  # For testing
    
    if success:
        state["email_otp_sent"] = True
    else:
        state["email_otp_sent_failed"] = True
        state["messages"].append(AIMessage(content=cleo_engagement.otp_failure_message))
    
    return state


def ask_email_otp_node(state: ChatbotState) -> ChatbotState:
    """Ask user to enter email OTP code"""
    
    print("ask_email_otp_node called")

    # Wrong attempt — error already sent by verify_email_otp_node, just interrupt
    if state.get("email_otp_attempts", 0) > 0:
        return {}

    state["messages"].append(AIMessage(content="I've sent a 6-digit verification code to that email. Enter it here to confirm."))
    
    return state


def verify_email_otp_node(state: ChatbotState) -> ChatbotState:
    """Verify the email OTP code entered by user"""
    
    print("verify_email_otp_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip()
        
        # Check for resend request
        if user_input.lower() in ["resend", "send again", "resend code"]:
            state["email_otp_attempts"] = 0  # Reset attempts for resend
            # Will trigger resend in router
            return state
        
        # Verify OTP
        stored_code = state.get("email_otp_code", "")
        timestamp = state.get("email_otp_timestamp", 0)
        
        is_valid, error = verify_otp(user_input, stored_code, timestamp, "email")
        
        if is_valid:
            state["email_verified"] = True
            state["messages"].append(AIMessage(content=cleo_engagement.email_success_message))
        else:
            state["email_otp_attempts"] += 1
            attempts = state["email_otp_attempts"]
            
            if error == "expired":
                state["messages"].append(AIMessage(content=cleo_engagement.otp_expired_message))
                
                state["email_otp_attempts"] = 0  # Reset for resend
            elif error == "invalid_format":
                state["messages"].append(AIMessage(content="Format is Invalid!"))
            elif error == "incorrect":
                if attempts >= 3:
                    state["messages"].append(AIMessage(content=cleo_engagement.email_otp_failure_message))
                    state["email_otp_attempts"]   = 0
                    state["email_validation_failed"] = True
                else:
                    state["messages"].append(AIMessage(
                        content=f"Hmm, that code didn't work. Please enter a correct 6-digit code (numbers only). (Attempt {attempts}/3)"
                    ))
    
    return state


def email_otp_router(state: ChatbotState) -> Literal["ask_phone", "send_email_otp", "ask_email", "ask_email_otp"]:
    """Route based on email OTP verification status"""
    
    print("email_otp_router called")

    if state.get("email_otp_sent_failed") == True:
        return "ask_email"
    
    # Check if verified
    if state.get("email_verified"):
        return "ask_phone"

    # 3 failures — verify_email_otp_node already reset attempts and set this flag
    if state.get("email_validation_failed"):
        return "ask_email"    
    
    # Check if need to resend (expired or user requested)
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip().lower()
        if "resend" in user_input or "send again" in user_input:
            return "send_email_otp"
    
    # Check if expired
    if is_otp_expired(state.get("email_otp_timestamp", 0), "email"):
        return "send_email_otp"


    
    # Continue asking for OTP
    return "ask_email_otp"


# ==================== PHONE OTP VERIFICATION NODES ====================

def send_phone_otp_node(state: ChatbotState) -> ChatbotState:
    """Generate and send OTP to phone via SMS"""
    
    print("send_phone_otp_node called")

    # ── Reset stale OTP state ─────────────────────────────────────────────────
    state["phone_otp_sent_failed"] = False
    state["phone_otp_attempts"]    = 0
    # ─────────────────────────────────────────────────────────────────────────
    
    phone = state["personal_details"].get("phone", "")

    otp_code = "444444"  # For testing
    state["phone_otp_code"] = otp_code

    # Create Plivo Verify session (Plivo generates + sends OTP internally)
    # session_uuid = create_phone_verify_session(phone)

    # if session_uuid:
    #     state["phone_verify_session_uuid"] = session_uuid
    #     state["phone_otp_sent"] = True
    #     message = f"I'm sending a 6-digit verification text now. Enter the code below to confirm."
    # else:
    #     state["phone_otp_sent_failed"] = True
    #     message = cleo_engagement.otp_failure_message
    
    # state["messages"].append(AIMessage(content=message))
    # state["messages"].append(AIMessage(content=f"I'm sending a 6-digit verification text now. Enter the code below to confirm."))  # for testing without Plivo
    
    return state


def ask_phone_otp_node(state: ChatbotState) -> ChatbotState:
    print("ask_phone_otp_node called")

    # Wrong attempt — error already sent by verify_phone_otp_node, just interrupt
    if state.get("phone_otp_attempts", 0) > 0:
        return {}

    state["messages"].append(AIMessage(
        content="I'm sending a 6-digit verification text now. Enter the code below to confirm."
    ))
    return state

    
# def ask_phone_otp_node(state: ChatbotState) -> ChatbotState:
#     """Ask user to enter phone OTP code"""
    
#     print("ask_phone_otp_node called")

#     # Wrong attempt — error already sent by verify_phone_otp_node, just interrupt
#     if state.get("phone_otp_attempts", 0) > 0:
#         return {}

#     if state.get("phone_otp_attempts") >= 1:
#         state["messages"].append(AIMessage(content="I can also resend the text. Just type 'resend' if you want me to send it again."))
#     else:
#         state["messages"].append(AIMessage(content=f"I'm sending a 6-digit verification text now. Enter the code below to confirm."))
    
#     return state


def verify_phone_otp_node(state: ChatbotState) -> ChatbotState:
    print("verify_phone_otp_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip()

        # Check for resend request
        if user_input.lower() in ["resend", "send again", "resend code"]:
            state["phone_otp_attempts"] = 0
            return state

        otp_input = user_input.strip()

        # ── TESTING MODE: static OTP ────────────────────────────────
        stored_otp = state.get("phone_otp_code", "")
        is_valid = (otp_input == stored_otp)
        error = "none" if is_valid else "incorrect"

        # ── PRODUCTION MODE: uncomment below ──────────────────────────────────────
        # if not otp_input.isdigit() or len(otp_input) != 6:
        #     state["messages"].append(AIMessage(content="Please enter a 6-digit code (numbers only)."))
        #     return state
        # session_uuid = state.get("phone_verify_session_uuid", "")
        # is_valid, error = validate_phone_otp(session_uuid, otp_input)
        # ─────────────────────────────────────────────────────────────────────

        if is_valid:
            state["phone_verified"] = True
            state["acknowledgement_type"] = "questions"
        else:
            state["phone_otp_attempts"] += 1
            attempts = state["phone_otp_attempts"]

            if error == "expired":
                state["messages"].append(AIMessage(content=cleo_engagement.otp_expired_message))
                state["phone_otp_attempts"] = 0
            elif error == "incorrect":
                if attempts >= 3:
                    state["phone_otp_attempts"] = 0
                    state["phone_validation_failed"] = True
                    state["messages"].append(AIMessage(content=cleo_engagement.phone_otp_failure_message))
                else:
                    state["messages"].append(AIMessage(
                        content=f"The code was incorrect. Kindly enter the correct code. (Attempt {attempts}/3)"
                    ))
            else:
                state["messages"].append(AIMessage(content=cleo_engagement.otp_failure_message))

    return state


def phone_otp_router(state: ChatbotState) -> Literal["acknowledgement","send_phone_otp", "ask_phone", "ask_phone_otp", "__end__"]:
    """Route based on phone OTP verification status"""
    
    print("phone_otp_router called")

    if state.get("phone_otp_sent_failed") == True:
        print("Phone OTP not sent yet, asking for phone again.")
        return "acknowledgement"

    # Check if verified
    if state.get("phone_verified", False):
        return "acknowledgement"

    if state.get("phone_validation_failed"):
        return "ask_phone"    
    
    # Check if need to resend (expired or user requested)
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip().lower()
        if "resend" in user_input or "send again" in user_input:
            return "send_phone_otp"
    
    # Continue asking for OTP
    return "ask_phone_otp"


# ==================== WORK EXPERIENCE COLLECTION ====================

def ask_work_experience_node(state: ChatbotState) -> ChatbotState:
    print("ask_work_experience_node called")

    question = (
        "Have you held other roles before (beyond what we've already discussed)?"
        if state.get("job_type") in ["server", "cook"]
        else "Do you have any prior work experience in this field?"
    )

    attempts = state.get("re_ask_attempts", {}).get("work_experience", 0)

    if attempts > 0:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        reask = generate_reask_message(question, user_input)
        state["messages"].append(AIMessage(content=reask))
    else:
        state["messages"].append(AIMessage(content=question))

    return state


def collect_work_experience_data_node(state: ChatbotState) -> ChatbotState:
    """Work experience already stored in state by main.py — just acknowledge"""
    print("collect_work_experience_data_node called")
    state["messages"].append(AIMessage(content="Thanks! Work experience saved. 💼"))
    return state


def store_work_experience_response_node(state: ChatbotState) -> ChatbotState:
    print("store_work_experience_response_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()
    question = (
        "Have you held other roles before (beyond what we've already discussed)?"
        if state.get("job_type") in ["server", "cook"]
        else "Do you have any prior work experience in this field?"
    )

    result = interpret_response(question, user_input, "yes_no")

    if result["intent"] == "ambiguous":
        attempts = state["re_ask_attempts"].get("work_experience", 0) + 1
        state["re_ask_attempts"]["work_experience"] = attempts
        print(f"[WORK_EXP] Ambiguous attempt {attempts}: {user_input}")

        if attempts >= 3:
                print(f"[WORK_EXP] 3 attempts — ending conversation")
                state["re_ask_attempts"].pop("work_experience", None)
                state["messages"].append(AIMessage(content=GENERIC_AMBIGUITY_FAIL_MESSAGE))
                state["generic_fail"] = True
                return state
        return state

    # Clear answer
    state["re_ask_attempts"].pop("work_experience", None)
    state["knockout_answers"]["Do you have any prior work experience in this field?"] = result["clean"]

    if result["intent"] == "yes":
        state["show_work_experience_ui"] = True
        state["messages"].append(AIMessage(content="Great! Please provide your most recent work experience details below."))
    else:
        state["show_work_experience_ui"] = False
        state["messages"].append(AIMessage(content="No problem, we'll move on! 👍"))

    return state


def work_experience_router(state: ChatbotState) -> Literal["ask_work_experience", "collect_work_experience_data", "ask_education", "__end__"]:
    if state.get("generic_fail"):
        return "__end__"
    if "work_experience" in state.get("re_ask_attempts", {}):
        return "ask_work_experience"
    if state.get("show_work_experience_ui"):
        return "collect_work_experience_data"
    return "ask_education" 

# ==================== EDUCATION COLLECTION ====================

def ask_education_node(state: ChatbotState) -> ChatbotState:
    """Ask about education level"""
    
    print("ask_education_node called")
    
    question = "What is the highest level of education you completed, and approximately when?"
    state["messages"].append(AIMessage(content=question))
    state["show_education_ui"] = True  # Signal to show checkbox UI
    
    return state


def store_education_node(state: ChatbotState) -> ChatbotState:
    print("store_education_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if isinstance(last_message, HumanMessage):
        content = last_message.content.strip()

        # Parse "College degree, 2018" → level + year
        if ',' in content:
            parts = content.split(',', 1)
            state["education_level"] = parts[0].strip()
            state["education_year"]  = parts[1].strip()
        else:
            state["education_level"] = content
            state["education_year"]  = "Not specified"

        print(f"Education level: {state['education_level']}, year: {state['education_year']}")
        state["messages"].append(AIMessage(content="Thanks! Saved. 🎓"))

    return state

def education_router(state: ChatbotState) -> Literal["ask_certifications", "ask_referral"]:
    
    if state.get("job_type") == "painter":
        return "ask_referral"
    
    return "ask_certifications" 


# ==================== CERTIFICATIONS ====================

def ask_certifications_node(state: ChatbotState) -> ChatbotState:
    print("ask_certifications_node called")

    question = "Do you have any relevant certifications? (Examples: ServSafe, TIPS, or CPR.)"
    attempts = state.get("re_ask_attempts", {}).get("certifications", 0)

    if attempts > 0:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        reask = generate_reask_message(question, user_input)
        state["messages"].append(AIMessage(content=reask))
    else:
        state["messages"].append(AIMessage(content=question))

    return state


def store_certifications_node(state: ChatbotState) -> ChatbotState:
    print("store_certifications_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()

    # LLM classifies: decline, certifications, or ambiguous
    prompt = f"""A job applicant was asked: "Do you have any relevant certifications?"
Their response: "{user_input}"

Classify their response as one of:
- "decline" — they said no, none, don't have any, or don't want to share
- "certifications" — they mentioned one or more actual certifications
- "ambiguous" — completely unclear or gibberish

Return ONLY one word: decline, certifications, or ambiguous."""

    try:
        resp = evaluation_llm.invoke(prompt)
        intent = resp.content.strip().lower()
    except Exception:
        intent = "certifications"

    if intent == "ambiguous":
        attempts = state["re_ask_attempts"].get("certifications", 0) + 1
        state["re_ask_attempts"]["certifications"] = attempts
        print(f"[CERT] Ambiguous attempt {attempts}: {user_input}")

        if attempts >= 3:
            print(f"[CERT] 3 attempts — ending conversation")
            state["re_ask_attempts"].pop("certifications", None)
            state["messages"].append(AIMessage(content=GENERIC_AMBIGUITY_FAIL_MESSAGE))
            state["generic_fail"] = True
            return state
        return state                                                       # ← fix: was missing

    if intent == "decline":
        state["certifications"] = []
        state["re_ask_attempts"].pop("certifications", None)
        state["messages"].append(AIMessage(content="No problem! Moving on. 👍"))
        return state

    # intent == "certifications" — extract name + date
    extract_prompt = f"""Extract certifications from this text. Return a JSON array of objects with "name" and "date" keys.
If no date is mentioned use "Not specified".
Text: "{user_input}"
Return ONLY the JSON array, nothing else. Example: [{{"name": "ServSafe", "date": "2023"}}]"""

    try:
        extract_resp = llm.invoke([HumanMessage(content=extract_prompt)])
        import json as _json
        certs = _json.loads(extract_resp.content.strip())
        state["certifications"] = certs if isinstance(certs, list) else []
    except Exception:
        state["certifications"] = [{"name": user_input, "date": "Not specified"}]

    state["re_ask_attempts"].pop("certifications", None)
    state["messages"].append(AIMessage(content="Thank you! Saved. 📋"))
    return state


def certifications_router(state: ChatbotState) -> Literal["ask_certifications", "ask_referral", "__end__"]:
    if state.get("generic_fail"):
        return "__end__"
    if "certifications" in state.get("re_ask_attempts", {}):
        return "ask_certifications"
    return "ask_referral"


def ask_referral_node(state: ChatbotState) -> ChatbotState:
    print("ask_referral_node called")

    question = "How did you hear about us? If you were referred by a current employee or resident, please let us know their name."
    attempts = state.get("re_ask_attempts", {}).get("referral", 0)

    if attempts > 0:
        last_human = next(
            (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
            None
        )
        user_input = last_human.content if last_human else ""
        reask = generate_reask_message(question, user_input)
        state["messages"].append(AIMessage(content=reask))
    else:
        state["messages"].append(AIMessage(content=question))

    return state


def store_referral_node(state: ChatbotState) -> ChatbotState:
    print("store_referral_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_input = last_message.content.strip()
    question = "How did you hear about us? If you were referred by a current employee or resident, please let us know their name."

    # ── Single LLM call: classify response ───────────────────────────────────
    prompt = f"""A job applicant was asked: "{question}"
Their response: "{user_input}"

Classify their response into exactly one of these three categories:

- "VALID" — any meaningful answer about how they heard about the job. This includes:
  job platforms (LinkedIn, Indeed, Glassdoor, ZipRecruiter), social media (Instagram, Facebook, TikTok),
  a person's name or "referred by someone", word of mouth, friend, family, Google, website, flyer, sign,
  or any recognizable source.

- "DECLINE" — they are explicitly refusing or have nothing to share. This includes:
  "no", "nope", "skip", "n/a", "none", "I don't know", "not sure", "don't want to say", "prefer not to".

- "AMBIGUOUS" — completely unclear, random characters, gibberish, or unrelated text that is
  neither a recognizable source nor a clear refusal.

Return ONLY one word: VALID, DECLINE, or AMBIGUOUS."""

    try:
        resp = evaluation_llm.invoke(prompt)
        classification = resp.content.strip().upper()
        print(f"[REFERRAL] Classification: {classification} for: {user_input}")
    except Exception:
        classification = "VALID"  # fail open

    # ── Decline — move forward silently ──────────────────────────────────────
    if classification == "DECLINE":
        print(f"[REFERRAL] Clear decline — moving forward")
        state["referral_source"] = "N/A"
        state["re_ask_attempts"].pop("referral", None)
        return state

    # ── Ambiguous — re-ask up to 3 times ─────────────────────────────────────
    if classification == "AMBIGUOUS":
        attempts = state["re_ask_attempts"].get("referral", 0) + 1
        state["re_ask_attempts"]["referral"] = attempts
        print(f"[REFERRAL] Ambiguous attempt {attempts}: {user_input}")

        if attempts >= 3:
            print(f"[REFERRAL] 3 attempts — ending conversation")
            state["re_ask_attempts"].pop("referral", None)
            state["messages"].append(AIMessage(content=GENERIC_AMBIGUITY_FAIL_MESSAGE))
            state["generic_fail"] = True
            return state
        return state

    # ── Valid — store and acknowledge ─────────────────────────────────────────
    state["referral_source"] = user_input
    state["re_ask_attempts"].pop("referral", None)
    state["messages"].append(AIMessage(content="Thanks! Noted. 🙌"))
    return state


def referral_router(state: ChatbotState) -> Literal["ask_referral", "ask_military", "__end__"]:
    if state.get("generic_fail"):
        return "__end__"
    if "referral" in state.get("re_ask_attempts", {}):
        return "ask_referral"
    if not state.get("referral_source", ""):
        return "ask_referral"
    return "ask_military"


# ==================== MILITARY SERVICE ====================

def ask_military_node(state: ChatbotState) -> ChatbotState:
    print("ask_military_node called")

    if state.get("military_served") and not state.get("military_follow_up_done"):
        question = "Thank you for your service 🇺🇸 Could you optionally share your Branch, Duty Status, and Rank? Or just say 'Skip' to continue."
        attempts = state.get("re_ask_attempts", {}).get("military_followup", 0)

        if attempts > 0:
            last_human = next(
                (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
                None
            )
            user_input = last_human.content if last_human else ""
            reask = generate_reask_message(question, user_input)
            state["messages"].append(AIMessage(content=reask))
        else:
            state["messages"].append(AIMessage(content=question))

    else:
        question = "One optional question 💙 — Have you ever served in the U.S. military?"
        attempts = state.get("re_ask_attempts", {}).get("military_initial", 0)

        if attempts > 0:
            last_human = next(
                (m for m in reversed(state["messages"]) if isinstance(m, HumanMessage)),
                None
            )
            user_input = last_human.content if last_human else ""
            reask = generate_reask_message(question, user_input)
            state["messages"].append(AIMessage(content=reask))
        else:
            state["messages"].append(AIMessage(content=question))

    return state


def store_military_node(state: ChatbotState) -> ChatbotState:
    print("store_military_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_text = last_message.content.strip()

    if not state.get("military_served"):
        # ── Initial yes/no question ───────────────────────────────────────────
        question = "Have you ever served in the U.S. military?"
        result = interpret_response(question, user_text, "yes_no")

        if result["intent"] == "ambiguous":
            attempts = state["re_ask_attempts"].get("military_initial", 0) + 1
            state["re_ask_attempts"]["military_initial"] = attempts
            print(f"[MILITARY] Ambiguous attempt {attempts}: {user_text}")

            if attempts >= 3:
                    print(f"[MILITARY] 3 attempts — ending conversation")
                    state["re_ask_attempts"].pop("military_initial", None)
                    state["messages"].append(AIMessage(content=GENERIC_AMBIGUITY_FAIL_MESSAGE))
                    state["generic_fail"] = True
        elif result["intent"] == "yes":
            state["military_served"] = True
            state["re_ask_attempts"].pop("military_initial", None)
        else:
            state["military_served"] = False
            state["military_follow_up_done"] = True
            state["re_ask_attempts"].pop("military_initial", None)

    else:
        # ── Follow-up: branch/duty/rank ───────────────────────────────────────
        follow_up_q = "military_followup"

        prompt = f"""A job applicant was asked: "Could you optionally share your Branch, Duty Status, and Rank? Or just say 'Skip' to continue."

Their response: "{user_text}"

Classify their response:
- "details" — they provided actual military information (branch, rank, duty status, or any combination)
- "skip"    — they want to skip (said skip, no, none, n/a, pass, not now, or similar)
- "ambiguous" — unclear, gibberish, or completely unrelated

Return ONLY valid JSON: {{"intent": "details" or "skip" or "ambiguous", "clean": "normalized details or skip"}}"""

        try:
            resp = llm.invoke([HumanMessage(content=prompt)])
            result = json.loads(resp.content.strip().replace("```json", "").replace("```", "").strip())
        except Exception:
            result = {"intent": "ambiguous", "clean": user_text}

        if result["intent"] == "details":
            state["military_details"] = {"details": result["clean"]}
            state["military_follow_up_done"] = True
            state["re_ask_attempts"].pop(follow_up_q, None)

        elif result["intent"] == "skip":
            state["military_follow_up_done"] = True
            state["re_ask_attempts"].pop(follow_up_q, None)

        else:
            attempts = state["re_ask_attempts"].get(follow_up_q, 0) + 1
            state["re_ask_attempts"][follow_up_q] = attempts
            print(f"[MILITARY FOLLOWUP] Ambiguous attempt {attempts}: {user_text}")

            if attempts >= 3:
                state["military_follow_up_done"] = True
                state["re_ask_attempts"].pop(follow_up_q, None)

    return state


def military_router(state: ChatbotState) -> Literal["ask_military", "ask_background_check", "score", "__end__"]:
    if state.get("generic_fail"):
        return "__end__"
    if "military_initial" in state.get("re_ask_attempts", {}):
        return "ask_military"
    if state.get("military_served") and not state.get("military_follow_up_done"):
        return "ask_military"
    if state.get("verification_required") == "true":
        return "ask_background_check"
    return "score"


# ==================== BACKGROUND CHECK CONSENT ====================

def ask_background_check_node(state: ChatbotState) -> ChatbotState:
    print("ask_background_check_node called")

    # Re-ask — message already sent by store_background_check_node
    if "background_check" in state.get("re_ask_attempts", {}):
        return {}

    # Initial ask
    state["messages"].append(AIMessage(
        content=(
            f"📋 {state['brand_name']} is required by Florida law to conduct a Level II background check through the Florida Clearinghouse for all employees. Employment is contingent on successful clearance. Are you comfortable with this requirement?"
        )
    ))
    return state


def store_background_check_node(state: ChatbotState) -> ChatbotState:
    print("store_background_check_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not isinstance(last_message, HumanMessage):
        return state

    user_text = last_message.content.strip()

    # ── Single LLM call: classify response ───────────────────────────────────
    prompt = f"""A job applicant was asked about consenting to a mandatory Level II background check
(fingerprint-based FBI/FDLE check) required by Florida state law for all employees.

Their response: "{user_text}"

Classify their response into exactly one of these three categories:

- "CONSENT" — they agree, understand, or are okay with the background check.
  Includes: "yes", "sure", "okay", "fine", "I agree", "no problem", "that's fine", "go ahead".

- "DECLINE" — they explicitly refuse or object to the background check.
  Includes: "no", "I don't agree", "I'm not comfortable", "refuse", "I won't", "skip".

- "AMBIGUOUS" — completely unclear, gibberish, unrelated, or cannot be determined.

Return ONLY one word: CONSENT, DECLINE, or AMBIGUOUS."""

    try:
        resp = llm.invoke([HumanMessage(content=prompt)])
        classification = resp.content.strip().upper()
        print(f"[BGC] Classification: {classification} for: {user_text}")
    except Exception:
        classification = "AMBIGUOUS"

    # ── Consent ───────────────────────────────────────────────────────────────
    if classification == "CONSENT":
        state["background_check_consented"] = True
        state["re_ask_attempts"].pop("background_check", None)
        state["messages"].append(AIMessage(content="Got it — understood. ✅ Let's continue!"))
        return state

    # ── Decline ───────────────────────────────────────────────────────────────
    if classification == "DECLINE":
        state["background_check_consented"] = False
        state["re_ask_attempts"].pop("background_check", None)
        state["messages"].append(AIMessage(
            content="That's a state requirement for all employees here. I'll end the application here for now — thank you so much for your time! 🙏"
        ))
        return state

    # ── Ambiguous — re-ask up to 3 times ─────────────────────────────────────
    attempts = state["re_ask_attempts"].get("background_check", 0) + 1
    state["re_ask_attempts"]["background_check"] = attempts
    print(f"[BGC] Ambiguous attempt {attempts}: {user_text}")

    if attempts >= 3:
        print(f"[BGC] 3 attempts — ending conversation")
        state["re_ask_attempts"].pop("background_check", None)
        state["background_check_consented"] = False
        state["messages"].append(AIMessage(content="This check is required by Florida state law for all employees. Thank you for your time! 🙏"))
        return state

    reask = generate_reask_message(
        "Are you okay with a mandatory Level II background check required by Florida state law?",
        user_text
    )
    state["messages"].append(AIMessage(content=reask))
    return state



def background_check_router(state: ChatbotState) -> Literal["ask_background_check", "ask_id_verification", "score", "__end__"]:
    print("background_check_router called")

    # Ambiguous after 3 attempts — end
    if not state.get("background_check_consented") and \
       not state.get("re_ask_attempts", {}).get("background_check") and \
       state.get("background_check_consented") is False and \
       "background_check" not in state.get("re_ask_attempts", {}):
        pass  # fall through to normal checks

    # Re-ask — still waiting for clear answer
    if "background_check" in state.get("re_ask_attempts", {}):
        return "ask_background_check"

    # Consented — continue
    if state.get("background_check_consented"):
        return "ask_id_verification"

    # Declined or 3 ambiguous — route to score (as per your design)
    return "score"



# ==================== ID VERIFICATION NODES ====================
async def ask_id_verification_node(state: ChatbotState) -> ChatbotState:
    print("ask_id_verification_node called")

    applicant_name  = state["personal_details"].get("name", "")
    phone           = state["personal_details"].get("phone", "")
    cleo_session_id = state.get("session_id", "")
    thread_id       = state.get("session_id", "")  # use session_id as proxy

    verify_link, simplici_session_id = create_id_verify_session(
        cleo_session_id, applicant_name, phone
    )

    if not verify_link:
        state["id_verify_failed"] = True
        state["messages"].append(AIMessage(
            content="We're experiencing a brief technical issue with our verification system. Our team will follow up with you directly."
        ))
        asyncio.create_task(log_id_verification_event(
            session_id=cleo_session_id, thread_id=thread_id,
            status="id_verify_session_failed",
            raw_data={"applicant_name": applicant_name, "phone": phone},
            error="create_id_verify_session returned empty link"
        ))
        return state

    state["id_verify_link"]       = verify_link
    state["id_verify_session_id"] = simplici_session_id

    # Log session created
    asyncio.create_task(log_id_verification_event(
        session_id=cleo_session_id, thread_id=thread_id,
        status="id_verify_session_created",
        raw_data={"simplici_session_id": simplici_session_id, "verify_link": verify_link}
    ))

    state["messages"].append(AIMessage(content="You're doing great! We're almost at the finish line. 🏁"))
    state["messages"].append(AIMessage(content="To keep our hiring process secure and get you onboarded quickly, we just need to verify your ID. It's a simple 30-second check where you'll snap a photo of your ID and a quick selfie to confirm it's really you."))
    state["messages"].append(AIMessage(content="Please make sure you're in a well-lit room and have your government-issued ID ready. Tap the button below to start! I'll be right here when you're back."))
    state["show_id_verify_ui"] = True

    # Log waiting for webhook
    asyncio.create_task(log_id_verification_event(
        session_id=cleo_session_id, thread_id=thread_id,
        status="id_verify_waiting",
        raw_data={"simplici_session_id": simplici_session_id}
    ))

    await save_session_mapping(simplici_session_id, cleo_session_id)
    return state


def process_id_result_node(state: ChatbotState) -> ChatbotState:
    """Send success or failure message based on webhook result"""

    print("process_id_result_node called")

    if state.get("id_verified"):
        state["messages"].append(AIMessage(
            content="Awesome news! Your identity verification is all set. 🛡️"
        ))
        state["messages"].append(AIMessage(
            content="That was the last big step. It's a huge help in getting your file ready for the store manager to review."
        ))
    else:
        # System flag / failure — move to manual review, don't block applicant
        state["messages"].append(AIMessage(
            content="It looks like our automated system is having a bit of trouble confirming the verification details right now."
            
        ))
        state["messages"].append(AIMessage(
            content="Don't worry! I've flagged your application for a manual review by our hiring team. They'll take a look at the documents you provided and reach out if they need anything else."
        ))

    return state

def id_verification_router(state: ChatbotState) -> Literal["score"]:
    """Route to next question or scoring"""
    
    print("id_verification_router called")

    return "score"



# ==================== SCORING & SUMMARY ====================

def score_node(state: ChatbotState) -> ChatbotState:
    print("score_node called")

    # Merge all answer sources into one dict for scoring
    answers = {}

    # Screening question answers
    answers.update(state.get("answers", {}))

    # Knockout question answers (candidates reached here = passed all)
    knockout_questions = state.get("knockout_questions", [])
    knockout_answers   = state.get("knockout_answers", {})
    
    for q in knockout_questions:
        answers[q] = knockout_answers.get(q, "Yes")

    # Background check consent
    answers["background_check_consent"] = "Yes" if state.get("background_check_consented") else "No"

    # Certifications
    certs = state.get("certifications", [])
    if certs:
        cert_names = ", ".join([c.get("name", "") for c in certs])
        answers["certifications"] = cert_names
    else:
        answers["certifications"] = "None"

    work_experience = state.get("work_experience", [])
    # Total years of work experience
    if work_experience:
        from datetime import datetime
        total_months = 0
        for exp in work_experience:
            try:
                start = datetime.strptime(exp.get("startDate", ""), "%Y-%m")
                end_str = exp.get("endDate", "").strip().lower()
                end = datetime.now() if end_str in ("present", "current", "") else datetime.strptime(end_str, "%Y-%m")
                total_months += (end.year - start.year) * 12 + (end.month - start.month)
            except Exception:
                pass
        total_years = round(total_months / 12, 1)
    else:
        total_years = 0.0

    answers["server_experience_years"] = f"{total_years} years"
    answers["cook_experience_years"]   = f"{total_years} years"    

    scoring_model = state["scoring_model"]

    print("Merged Answers:", answers)
    print("Scoring Model:", scoring_model)

    answers_str = json.dumps(answers, indent=2)
    scoring_str = json.dumps(scoring_model, indent=2)

    # Dynamically calculate total_score from scoring model weights
    total_possible = sum(
        rule.get("weight", 0) 
        for rule in scoring_model.values() 
        if isinstance(rule, dict)
    )

    prompt = SCORING_PROMPT.format(
        answers=answers_str,
        scoring_model=scoring_str,
        total_score=total_possible     
    )
    response = llm.invoke(prompt)
    print("Scoring node response:", response.content)

    try:
        score_text = response.content.strip()
        if score_text.startswith("```json"):
            score_text = score_text.replace("```json", "").replace("```", "").strip()
        elif score_text.startswith("```"):
            score_text = score_text.replace("```", "").strip()

        result = json.loads(score_text)

        state["scores"]      = result["scores"]
        state["total_score"] = total_possible

        state["score"] = sum(result["scores"].values())

        print("Calculated score:", state["score"])
        print("Calculated total_score:", total_possible)

    except json.JSONDecodeError:
        state["scores"]      = {}
        state["score"]       = 0
        state["total_score"] = total_possible

    return state

def summary_node(state: ChatbotState) -> ChatbotState:
    """Generate comprehensive JSON report and send to XANO"""
    
    print("summary_node called")
    
    # Extract data from state
    name = state["personal_details"].get("name", "Candidate")
    email = state["personal_details"].get("email", "")
    phone = state["personal_details"].get("phone", "")
    
    age = state.get("applicant_age", "")
    session_id = state.get("session_id", "")
    job_id = state.get("job_id", "")
    company_id = state.get("company_id", "")
    is_live = state.get("is_live", False)
    
    knockout_answers = state.get("knockout_answers", {})
    answers = state.get("answers", {})
    
    score = state.get("score", 0)
    total_score = state.get("total_score", 100)

    work_experiences = state.get("work_experience", [])
    education_level = state.get("education_level", "")

    
    # Convert score to percentage
    score = (score / total_score) * 100 if total_score > 0 else 0
    total_score = 100

    if score > 100:
        score = 100

    # Format knockout answers for prompt
    knockout_text = "\n".join([
        f"Q: {q}\nA: {a}" for q, a in knockout_answers.items()
    ])
    
    # Format screening answers for prompt
    answers_text = "\n".join([
        f"Q: {q}\nA: {a}" for q, a in answers.items()
    ])

    # Format work experiences for prompt
    work_exp_text = ""
    if work_experiences:
        work_exp_text = "\n".join([
            f"- {exp['role']} at {exp['company']} ({exp['startDate']} to {exp['endDate']})"
            for exp in work_experiences
        ])
    else:
        work_exp_text = "No prior work experience"

    print(f"Work Experience in state variable: {work_experiences}") 
    print(f"Work Experience formatted text:\n{work_exp_text}")

    # Extract all conversation messages
    all_messages = state.get("messages", [])
    conversation_history = []
    
    for msg in all_messages:
        if isinstance(msg, HumanMessage):
            conversation_history.append({
                "role": "user",
                "content": msg.content
            })
        elif isinstance(msg, AIMessage):
            conversation_history.append({
                "role": "ai",
                "content": msg.content
            })
    
    print(f"Conversation history length: {len(conversation_history)}")
    
    address = state.get("address", {})

    data = {
        "name": name,
        "email": email,
        "phone": phone,
        "session_id": session_id,
        "knockout_answers": knockout_text,
        "answers": answers_text,
        "score": score,
        "total_score": total_score,
        "work_experience": work_exp_text,
        "education": education_level,
        "address": address
    }

    json_report = generate_json_report(data)

    single_company = state.get("single_company", False)
    
    # Send to XANO
    send_applicant_to_xano(
        name=name,
        email=email,
        phone=phone,
        age = age,
        score=score,
        total_score=total_score,
        json_report=json_report,
        answers=answers,
        session_id=session_id,
        job_id=job_id,
        company_id=company_id,
        is_live=is_live,
        conversation_history=conversation_history,
        single_company=single_company
    )
    
    return state

def end_node(state: ChatbotState) -> ChatbotState:
    """End conversation"""
    
    print("end_node called")

    if state.get("incomplete_application"):
        state["messages"].append(AIMessage(content="One of our support team members will reach out to you shortly. It is difficult to complete the application at this time. Thanks! 🙏"))
        return state
        
    state["messages"].append(AIMessage(content=f"Great job! You've successfully completed the application. Your information has been securely saved and submitted to {state.get('brand_name')}."))

    state["delay_node_type"] = "end"

    return state

def post_end_router(state: ChatbotState) -> Literal["delay_messages", "__end__"]:
    
    if state.get("incomplete_application"):
        return "__end__"
    
    return "delay_messages"


# ==================== GRAPH BUILDER ====================

def build_graph(checkpointer):
    """Build the screening chatbot graph"""
    workflow = StateGraph(ChatbotState)
    
    # Add all nodes
    workflow.add_node("start", start_node)
    workflow.add_node("delay_messages", delay_messages_node)
    workflow.add_node("check_ready", check_ready_node)
    workflow.add_node("acknowledgement", acknowledge_node)
    workflow.add_node("reask_consent", reask_consent_node)
    
    workflow.add_node("ask_knockout_question", ask_knockout_question_node)
    workflow.add_node("store_kq_answer", store_kq_answer_node)
    
    workflow.add_node("evaluate_single_knockout", evaluate_single_knockout_node)

    workflow.add_node("ask_address", ask_address_node)
    workflow.add_node("store_address", store_address_node)
    workflow.add_node("ask_gps_verification", ask_gps_verification_node)
    workflow.add_node("process_gps", process_gps_node)
    
    workflow.add_node("ask_work_experience", ask_work_experience_node)
    workflow.add_node("store_work_experience_response", store_work_experience_response_node)
    workflow.add_node("collect_work_experience_data", collect_work_experience_data_node)
    
    workflow.add_node("ask_education", ask_education_node)
    workflow.add_node("store_education", store_education_node)

    workflow.add_node("ask_certifications",    ask_certifications_node)
    workflow.add_node("store_certifications",  store_certifications_node)
    workflow.add_node("ask_referral",   ask_referral_node)
    workflow.add_node("store_referral", store_referral_node)
    workflow.add_node("ask_military",          ask_military_node)
    workflow.add_node("store_military",        store_military_node)
    workflow.add_node("ask_background_check",  ask_background_check_node)
    workflow.add_node("store_background_check", store_background_check_node)
    
    workflow.add_node("ask_name", ask_name_node)
    workflow.add_node("store_name", store_name_node)
    workflow.add_node("ask_email", ask_email_node)
    workflow.add_node("store_email", store_email_node)
    
    workflow.add_node("send_email_otp", send_email_otp_node)
    workflow.add_node("ask_email_otp", ask_email_otp_node)
    workflow.add_node("verify_email_otp", verify_email_otp_node)
    workflow.add_node("ask_phone", ask_phone_node)
    workflow.add_node("store_phone", store_phone_node)
    workflow.add_node("send_phone_otp", send_phone_otp_node)
    workflow.add_node("ask_phone_otp", ask_phone_otp_node)
    workflow.add_node("verify_phone_otp", verify_phone_otp_node)

    workflow.add_node("ask_id_verification", ask_id_verification_node)
    workflow.add_node("process_id_result",   process_id_result_node)

    workflow.add_node("ask_question", ask_question_node)
    workflow.add_node("store_answer", store_answer_node)
    
    workflow.add_node("score", score_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("end", end_node)
    
    # ======================== Build flow ==========================================
    
    # Set entry point
    workflow.set_entry_point("start")
    
    workflow.add_edge("start", "delay_messages")
    workflow.add_conditional_edges("delay_messages", post_delay_router)
    workflow.add_edge("reask_consent", "check_ready")
    
    workflow.add_conditional_edges("check_ready", ready_router)

    # Knockout Questions loop
    workflow.add_conditional_edges("acknowledgement", post_acknowledgement_router)
    
    workflow.add_edge("ask_knockout_question", "store_kq_answer")
    workflow.add_conditional_edges("store_kq_answer", kq_ambiguity_router)
    workflow.add_conditional_edges("evaluate_single_knockout", single_knockout_router, {
    "ask_knockout_question": "ask_knockout_question",
    "ask_question":          "ask_question",
    "ask_address":           "ask_address",
    "__end__":               END,
    })

    # Questions loop
    workflow.add_edge("ask_question", "store_answer")
    workflow.add_conditional_edges("store_answer", answer_router, {
        "ask_question":   "ask_question",
        "ask_address":    "ask_address",    # ← add this
        "__end__":        END,
    })

    # Address + GPS flow (between phone verification and questions)
    workflow.add_edge("ask_address", "store_address")
    workflow.add_edge("store_address", "ask_gps_verification")
    workflow.add_edge("ask_gps_verification", "process_gps")
    workflow.add_conditional_edges("process_gps", gps_router)

    # Personal details flow with validation
    workflow.add_edge("ask_name", "store_name")
    workflow.add_conditional_edges("store_name", name_router)
    workflow.add_edge("ask_email", "store_email")

    workflow.add_conditional_edges("store_email", email_router, {
        "ask_email":      "ask_email",
        "send_email_otp": "send_email_otp",
        "__end__":        END,
    })
    
    # Email OTP verification flow
    workflow.add_conditional_edges("send_email_otp", email_otp_router)
    workflow.add_edge("ask_email_otp", "verify_email_otp")
    workflow.add_conditional_edges("verify_email_otp", email_otp_router)
    
    workflow.add_edge("ask_phone", "store_phone")
    workflow.add_conditional_edges("store_phone", phone_router, {
    "ask_phone":      "ask_phone",
    "send_phone_otp": "send_phone_otp",
    "__end__":        END,
    })
    
    # Phone OTP verification flow
    workflow.add_conditional_edges("send_phone_otp", phone_otp_router)
    workflow.add_edge("ask_phone_otp", "verify_phone_otp")

    workflow.add_conditional_edges("verify_phone_otp", phone_otp_router, {
    "acknowledgement": "acknowledgement",
    "send_phone_otp":  "send_phone_otp",
    "ask_phone":       "ask_phone",
    "ask_phone_otp":   "ask_phone_otp",
    "__end__":         END,
    })

    # Work experience flow
    workflow.add_edge("ask_work_experience", "store_work_experience_response")
    
    workflow.add_conditional_edges("store_work_experience_response", work_experience_router, {
    "ask_work_experience":      "ask_work_experience",
    "collect_work_experience_data": "collect_work_experience_data",
    "ask_education":            "ask_education",
    "__end__":                  END,
    })
    
    workflow.add_edge("collect_work_experience_data", "ask_education")

    # Education flow
    workflow.add_edge("ask_education", "store_education")
    
    workflow.add_conditional_edges("store_education", education_router, {
        "ask_certifications": "ask_certifications",
        "ask_referral":       "ask_referral",
    })
    
    # Certifications and military service flow
    workflow.add_edge("ask_certifications", "store_certifications")

    workflow.add_conditional_edges("store_certifications", certifications_router, {
    "ask_certifications": "ask_certifications",
    "ask_referral":       "ask_referral",
    "__end__":            END,
    })
    
    workflow.add_edge("ask_referral", "store_referral")
    
    workflow.add_conditional_edges("store_referral", referral_router, {
    "ask_referral":  "ask_referral",
    "ask_military":  "ask_military",
    "__end__":       END,
    })
    
    workflow.add_edge("ask_military", "store_military")
    workflow.add_conditional_edges("store_military", military_router, {
    "ask_military": "ask_military",
    "ask_background_check": "ask_background_check",
    "score": "score",
    "__end__": END,
    })
    
    # Background check flow
    workflow.add_edge("ask_background_check",    "store_background_check")

    workflow.add_conditional_edges("store_background_check", background_check_router, {
    "ask_background_check": "ask_background_check",
    "ask_id_verification":  "ask_id_verification",
    "score":                "score",
    "__end__":              END,
    })

    # ID Verification flow
    workflow.add_edge("ask_id_verification", "process_id_result")
    workflow.add_conditional_edges("process_id_result", id_verification_router)

    # Scoring and end
    workflow.add_edge("score", "summary")
    workflow.add_edge("summary", "end")
    workflow.add_conditional_edges("end", post_end_router)
        
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["delay_messages", "reask_consent","ask_knockout_question",  "ask_address", "ask_gps_verification", "ask_work_experience", "ask_education", "ask_certifications", "ask_referral", "ask_military", "ask_background_check", "ask_name", "ask_email", "ask_email_otp", "ask_phone", "ask_phone_otp", "ask_id_verification", "ask_question"],
        interrupt_before=["collect_work_experience_data"]
    )
    
    return app