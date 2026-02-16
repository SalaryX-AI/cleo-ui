"""Main graph implementation for Cleo screening chatbot with human-in-the-loop"""


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


from otp_verification import (
    generate_otp, 
    send_email_otp, 
    send_sms_otp, 
    verify_otp,
    is_otp_expired,
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
    """Validate phone number with country code (+1, +92, etc.) and 10+ digits"""
    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)

    # Must start with + and contain only digits after, total digits >= 10
    return bool(re.match(r'^\+\d{10,}$', cleaned))



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

    session_id: str = ""
    job_id: str = ""
    company_id: str = ""

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


# ==================== Acknowledgement ====================
def acknowledge_node(state: ChatbotState) -> ChatbotState:
    """Send acknowledgment message"""
    print(f"acknowledge_node called (type: {state['acknowledgement_type']})")

    ack_type = state.get("acknowledgement_type", "default")

    ack_messages = cleo_engagement.ack_messages
    
    message = ack_messages.get(ack_type)

    state["messages"].append(AIMessage(content=message))
    
    return state


def post_acknowledgement_router(state: ChatbotState) -> Literal["ask_knockout_question", "ask_question"]:
    """Decide where to go after acknowledgement"""
    
    # If we're done with personal details, start questions
    if state.get("acknowledgement_type") == "questions":
        return "ask_question"
    
    # Otherwise, start knockout questions
    return "ask_knockout_question"


# ==================== Delay messages ====================

def delay_messages_node(state: ChatbotState) -> ChatbotState:
    """Node that adds delayed messages"""
    
    print(f"delay_messages_node called (type: {state['delay_node_type']})")
    
    delay_messages = {
        "greeting": [
            "Thanks for your interest — we're a friendly, locally-owned team. My job is to make your application process super fast and easy.",
            "I just need to ask a few quick screening questions - it'll take less than 3 minutes total. Ready to jump in?"
        ],
        "end": [
            "Our hiring team will take it from here. Your application will be carefully reviewed. If you are selected to move forward, we will contact you via email or phone to schedule an interview or conduct a brief background check prior to scheduling the interview.",
            f"You can expect to hear from us regarding your status within 1-2 business days. Thank you again for your time and interest in working with {state.get("brand_name")}."
        ],
        "default": "Let's continue!"
    }
    
    delay_node_type = state.get("delay_node_type", "default")
    messages = delay_messages.get(delay_node_type)
    
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
    
    state["messages"].append(AIMessage(content=f"Hello! I'm Cleo, the hiring assistant for {state['brand_name']}."))

    state["delay_node_type"] = "greeting"
    
    return state


def check_ready_node(state: ChatbotState) -> ChatbotState:
    """Process ready response"""

    print("check_ready_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.lower().strip()

        prompt = CONSENT_EVALUATION_PROMPT.format(user_response=user_input)
        response = llm.invoke(prompt)
        
        # Get LLM's decision (should be "Yes" or "No")
        llm_decision = response.content.strip()
        
        print(f"User said: '{user_input}' | LLM decision: '{llm_decision}'")
        
        if llm_decision.lower() == "yes":
            state["ready_confirmed"] = True
            state["acknowledgement_type"] = "ready"
        else:
            # Send decline message
            decline_message = cleo_engagement.decline_message
            state["messages"].append(AIMessage(content=decline_message))    
    
    return state


def ready_router(state: ChatbotState) -> Literal["ask_knockout_question", "__end__"]:
    """Route based on ready confirmation"""
    
    print("ready_router called")
    
    if state["ready_confirmed"]:
        return "ask_knockout_question"
    return "__end__" # go directly to END

# ==================== knockout questions ============================

def ask_knockout_question_node(state: ChatbotState) -> ChatbotState:
    """Ask knockout questions"""
    
    print("ask_knockout_question_node called")
    
    idx = state["current_knockout_question_index"]
    knockout_questions = state["knockout_questions"]
    
    if idx < len(knockout_questions):
        knockout_question = knockout_questions[idx]
        
        # prompt = ASK_KNOCKOUT_QUESTION_PROMPT.format(
        #     question=knockout_question,
        #     previous_question = knockout_questions[idx-1] if idx > 0 else "None",
        #     previous_answer = state["knockout_answers"][knockout_questions[idx-1]] if idx > 0 else "None",
        #     )

        # if idx == 0 or idx == 1:
        #     #  response = llm.invoke(prompt)
        #      state["messages"].append(AIMessage(content=knockout_question))
        # else:
        #     # Use the chat template
        #     messages = chat_template.format_messages(user_input=prompt)
        #     response = llm.invoke(messages)

        #     prompt = prompt + "\n(Note: This is the first question.)"
    
        #     state["messages"].append(AIMessage(content=response.content))

        state["messages"].append(AIMessage(content=knockout_question))
    
    return state


def store_kq_answer_node(state: ChatbotState) -> ChatbotState:
    """Store knockout answer and increment index"""
    
    print("store_kq_answer_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        idx = state["current_knockout_question_index"]
        if idx < len(state["knockout_questions"]):
            knockout_question = state["knockout_questions"][idx]
            
            if idx == 1:
                age = extract_age_from_text(last_message.content)
                print(f"Extracted age: {age}")
                state["knockout_answers"][knockout_question] = age
                state["applicant_age"] = age
                state["current_knockout_question_index"] += 1

                return state
            
            state["knockout_answers"][knockout_question] = last_message.content
            state["current_knockout_question_index"] += 1
    
    return state


# def knockout_question_router(state: ChatbotState) -> Literal["ask_knockout_question", "evaluate_knockout"]:
#     """Route to next knockout_question or evaluation"""
    
#     print("knockout_question_router called")
    
#     if state["current_knockout_question_index"] < len(state["knockout_questions"]):
#         return "ask_knockout_question"
#     return "evaluate_knockout"


# ==================== KNOCKOUT EVALUATION (Per Question) ====================

def evaluate_single_knockout_node(state: ChatbotState) -> ChatbotState:
    """Evaluate the most recent knockout answer"""
    
    print("evaluate_single_knockout_node called")
    
    knockout_questions = state["knockout_questions"]
    knockout_answers = state["knockout_answers"]
    current_index = state["current_knockout_question_index"] - 1  # We just stored it
    
    if current_index < 0 or current_index >= len(knockout_questions):
        return state
    
    current_question = knockout_questions[current_index]
    current_answer = knockout_answers.get(current_question, "No answer")
    
    print(f"Evaluating Q{current_index + 1}: {current_question}")
    print(f"Answer: {current_answer}")
    
    # Evaluate using LLM
    prompt = f"""
    Evaluate if this answer is positive (YES) or negative (NO).
    
    Question: {current_question}
    Answer: {current_answer}
    
    Rules:
    - Positive responses: "yes", "yeah", "yep", "sure", "I am", "I have", "I can", "available", numbers ≥18, "definitely", "of course"
    - Negative responses: "no", "not", "don't", "can't", "unavailable", numbers <18, "nope"
    - Incomplete but positive intent: "I'm", "yes I", "I do" → treat as YES
    
    Return ONLY "YES" or "NO". Nothing else.
    
    Decision:
    """
    
    response = llm.invoke(prompt)
    decision = response.content.strip().upper()
    
    print(f"Decision: {decision}")
    
    if decision == "NO":
        state["current_knockout_failed"] = True
        
        # Add specific failure message based on question index
        failure_messages = [
            "I understand. Unfortunately, we can only proceed with applicants who are legally eligible to work in the U.S. Thank you for your time!",
            "I understand. Unfortunately, the minimum age requirement is 18, so we can't move forward right now. Thank you for your time!",
            "I see. While we appreciate your interest, we currently only have openings for those specific shifts. Thank you for your time today.",
            "I see. Reliable transportation is crucial for those evening and weekend shifts, which can sometimes be difficult to reach. Unfortunately, this is a firm requirement for the role at this time. Thank you so much for taking the time to chat with me today!"
        ]
        
        failure_message = failure_messages[current_index] if current_index < len(failure_messages) else failure_messages[-1]
        state["messages"].append(AIMessage(content=failure_message))
    else:
        state["current_knockout_failed"] = False
        
        # Add specific acknowledgment based on question index
        acknowledgment_messages = [
            "Got it, thank you.",
            "Great, almost done with the requirements.",
            "Perfect! That sounds like a good fit for our team.",
            ""  # No acknowledgment for last question - just continue
        ]
        
        ack_message = acknowledgment_messages[current_index] if current_index < len(acknowledgment_messages) else ""
        
        if ack_message:
            state["messages"].append(AIMessage(content=ack_message))
    
    return state


def single_knockout_router(state: ChatbotState) -> Literal["ask_knockout_question", "ask_address", "__end__"]:
    """Route based on single knockout evaluation"""
    
    print("single_knockout_router called")
    
    # Check if current question failed
    if state.get("current_knockout_failed", False):
        return "__end__"  # End conversation
    
    # Check if more questions remain
    if state["current_knockout_question_index"] < len(state["knockout_questions"]):
        return "ask_knockout_question"  # Ask next question
    
    # All questions passed
    return "ask_address"  # Continue to work experience

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
                state["gps_verified"] = True
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
                    state["messages"].append(AIMessage(
                        content=f"Thanks for sharing! We noticed your current location appears to be about {result['distance_miles']:.1f} mile(s) from the address you provided. Can you confirm that {typed_address} is your correct home address?"
                    ))
                # else:
                #     state["messages"].append(AIMessage(
                #         content="Your location has been verified. Thank you!"
                #     ))
            else:
                # No address to compare, just accept GPS
                state["gps_verified"] = True
                state["messages"].append(AIMessage(
                    content="Location received, thank you!"
                ))

        except Exception as e:
            print(f"GPS processing error: {e}")
            # GPS failed gracefully - don't block flow
            state["gps_verified"] = True
            state["gps_flagged"] = True
            state["gps_flag_reason"] = "GPS data could not be processed"

    return state


def gps_router(state: ChatbotState) -> Literal["ask_work_experience", "ask_gps_verification"]:
    """
    Route after GPS processing.
    Flagged addresses get a soft clarifying question but still continue.
    This is never a hard stop - just flags for manual review.
    """
    print("gps_router called")
    # Always continue to questions regardless of flag
    # Flag is stored in state for XANO/hiring manager review
    return "ask_work_experience"

# ==================== WORK EXPERIENCE COLLECTION ====================

def ask_work_experience_node(state: ChatbotState) -> ChatbotState:
    """Ask about prior work experience"""
    
    print("ask_work_experience_node called")
    
    question = "Verified! You're definitely within range. Now, do you have any prior work experience in this field?"
    state["messages"].append(AIMessage(content=question))
    
    return state


def store_work_experience_response_node(state: ChatbotState) -> ChatbotState:
    """Store yes/no response and set flag for UI using LLM evaluation"""
    
    print("store_work_experience_response_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip()
        
        # Store the answer in knockout_answers
        state["knockout_answers"]["Do you have prior work experience?"] = last_message.content
        
        # Use LLM to evaluate the response
        prompt = f"""
        Evaluate if this answer indicates YES (has work experience) or NO (no work experience).
        
        Question: "Do you have prior work experience?"
        Answer: "{user_input}"
        
        Rules:
        - Positive responses (indicating YES): "yes", "yeah", "yep", "sure", "I have", "I do", "I worked", "definitely", "of course", mentions of specific jobs or companies
        - Negative responses (indicating NO): "no", "nope", "not", "don't", "never", "haven't", "no experience", "fresh graduate"
        - Unclear/Incomplete: treat as NO (user can provide details if needed)
        
        Examples:
        - "yes I have" → YES
        - "I worked at McDonald's" → YES
        - "yeah, 2 years" → YES
        - "no" → NO
        - "I'm a student" → NO (unclear, assume no)
        - "not really" → NO
        
        Return ONLY "YES" or "NO". Nothing else.
        
        Decision:
        """
        
        response = llm.invoke(prompt)
        decision = response.content.strip().upper()
        
        print(f"Work experience evaluation: {decision}")
        
        if decision == "YES":
            state["show_work_experience_ui"] = True
            # Add a message that will trigger the UI
            state["messages"].append(AIMessage(content="Great! Please provide your most recent work experience details below."))
        else:
            state["show_work_experience_ui"] = False
            # No work experience - continue normally without UI
    
    return state

# ==================== EDUCATION COLLECTION ====================

def ask_education_node(state: ChatbotState) -> ChatbotState:
    """Ask about education level"""
    
    print("ask_education_node called")
    
    question = "What is your highest level of education completed?"
    state["messages"].append(AIMessage(content=question))
    state["show_education_ui"] = True  # Signal to show checkbox UI
    
    return state


def store_education_node(state: ChatbotState) -> ChatbotState:
    """Store education level from user selection"""
    
    print("store_education_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        state["education_level"] = last_message.content
    
    print(f"Stored education level: {state['education_level']}")
    return state

# ==================== PERSONAL DETAILS COLLECTION ====================

def ask_name_node(state: ChatbotState) -> ChatbotState:
    """Ask for name"""
    
    print("ask_name_node called")

    ask_name = cleo_engagement.ask_name

    state["messages"].append(AIMessage(content=ask_name))
    
    return state


def store_name_node(state: ChatbotState) -> ChatbotState:
    """Store name from user input"""
    
    print("store_name_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        state["personal_details"]["name"] = last_message.content
    
    return state


# ==================== EMAIL COLLECTION ====================
def ask_email_node(state: ChatbotState) -> ChatbotState:
    """Ask for email (or re-ask if validation failed)"""
    
    print("ask_email_node called")
    
     # Check if validation failed
    if state.get("email_validation_failed"):
        
        # Check attempt count
        if state.get("email_attempt_count", 0) >= 3:
            
            # After 3 attempts, show example
            prompt = PERSONAL_DETAIL_REASK_WITH_EXAMPLE_PROMPT.format(
                detail_type="email",
                invalid_attempt=state.get("invalid_email_attempt"),
                example="john.doe@example.com"
            )
        else:
            
            # Normal re-ask (no example)
            prompt = PERSONAL_DETAIL_REASK_PROMPT.format(
                detail_type="email",
                invalid_attempt=state.get("invalid_email_attempt")
            )
    else:
        if state.get("email_otp_sent_failed") == True:
            state["messages"].append(AIMessage(content="Kindly enter your email address again (example: john.doe@example.com)"))

            state["email_otp_sent_failed"] = False
            return state
        
        # Use normal ask prompt
        prompt = PERSONAL_DETAIL_ASK_PROMPT.format(
            detail_type="email",
            previous_question="What is your full name?",
            previous_answer=state["personal_details"].get("name", "None")
        )
    
    # Use the chat template
    messages = chat_template.format_messages(user_input=prompt)
    response = llm.invoke(messages)    
    
    state["messages"].append(AIMessage(content=response.content))
    
    return state


def store_email_node(state: ChatbotState) -> ChatbotState:
    """Store email from user input with validation"""
    
    print("store_email_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_text = last_message.content.strip()

        # Extract email using LLM
        email = extract_email_from_text(user_text)
        
        print(f"Original input: {user_text}")  # Debug
        print(f"Extracted email: {email}")  # Debug
        
        # Validate email
        if validate_email(email):
            # Valid - store it
            state["personal_details"]["email"] = email
            state["email_validation_failed"] = False
            state["invalid_email_attempt"] = ""

            state["email_attempt_count"] = 0  # Reset counter
            
            print("Valid email stored:", email)
        else:
            # Invalid - set flag to re-ask
            state["email_validation_failed"] = True
            state["invalid_email_attempt"] = email

            state["email_attempt_count"] += 1  # Increment counter
            
            print("Invalid email detected:", email)
    
    return state


def email_router(state: ChatbotState) -> Literal["ask_email", "send_email_otp"]:
    """Check if email is valid, re-ask or continue"""
    
    print("email_router called")
    
    if state.get("email_validation_failed"):
        return "ask_email"  # Re-ask for email
    return "send_email_otp"  # Continue to email OTP verification


# ==================== PHONE COLLECTION ====================

def ask_phone_node(state: ChatbotState) -> ChatbotState:
    """Ask for phone (or re-ask if validation failed)"""
    
    print("ask_phone_node called")

    # Check if validation failed
    if state.get("phone_validation_failed"):
         
        # Check attempt count
        if state.get("phone_attempt_count") >= 3:
            # After 3 attempts, show example
            prompt = PERSONAL_DETAIL_REASK_WITH_EXAMPLE_PROMPT.format(
                detail_type="phone number",
                invalid_attempt=state.get("invalid_phone_attempt"),
                example="+1-234-567-8900"
            )

            # Use the chat template
            messages = chat_template.format_messages(user_input=prompt)
            response = llm.invoke(messages)
            
            state["messages"].append(AIMessage(content=response.content))
        else:
            # Normal re-ask (no example)
            prompt = PERSONAL_DETAIL_REASK_PROMPT.format(
                detail_type="phone number",
                invalid_attempt=state.get("invalid_phone_attempt")
            )

            # Use the chat template
            messages = chat_template.format_messages(user_input=prompt)
            response = llm.invoke(messages)
            
            state["messages"].append(AIMessage(content=response.content))
    else:
        
        # if state.get("phone_otp_sent_failed") == True:
        #     print("Re-asking for phone due to previous OTP send failure.")
        #     state["messages"].append(AIMessage(content="Kindly enter your phone number again with country code (example: +1-234-567-8900)"))

        #     state["phone_otp_sent_failed"] = False

        #     return state
        
        # Use normal ask prompt
        ask_phone = cleo_engagement.ask_phone
        state["messages"].append(AIMessage(content=ask_phone))
    
    return state


def store_phone_node(state: ChatbotState) -> ChatbotState:
    """Store phone from user input with validation"""
    
    print("store_phone_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_text = last_message.content.strip()

        # Extract phone using LLM
        phone = extract_phone_from_text(user_text)
        
        print(f"Original input: {user_text}")  # Debug
        print(f"Extracted phone: {phone}")  # Debug
        
        # Validate phone
        if validate_phone(phone):
            # Valid - store it
            state["personal_details"]["phone"] = phone
            state["phone_validation_failed"] = False
            state["invalid_phone_attempt"] = ""

            state["phone_attempt_count"] = 0  # Reset counter

            state["acknowledgement_type"] = "questions"

        else:
            # Invalid - set flag to re-ask
            state["phone_validation_failed"] = True
            state["invalid_phone_attempt"] = phone

            state["phone_attempt_count"] += 1  # Increment counter
    
    return state


def phone_router(state: ChatbotState) -> Literal["ask_phone", "send_phone_otp"]:
    """Check if phone is valid, re-ask or continue"""
    
    print("phone_router called")
    
    if state.get("phone_validation_failed", False):
        return "ask_phone"  # Re-ask for phone
    
    return "send_phone_otp"  # Continue to phone OTP verification


# ==================== EMAIL OTP VERIFICATION NODES ====================

def send_email_otp_node(state: ChatbotState) -> ChatbotState:
    """Generate and send OTP to email"""
    
    print("send_email_otp_node called")
    
    email = state["personal_details"].get("email", "")
    user_name = state["personal_details"].get("name")
    
    # Generate OTP
    otp_code = generate_otp()
    # otp_code = "123456"  # For testing
    
    # Store in state
    state["email_otp_code"] = otp_code
    state["email_otp_timestamp"] = time.time()
    brand_name = state.get("brand_name")
    
    # Send email
    success = send_email_otp(email, otp_code, brand_name, user_name)
    # success = True  # For testing
    
    if success:
        message = f"Okay, I've just sent a 6-digit verification code to {email}. Please check your inbox (and spam folder)"
        state["email_otp_sent"] = True
    else:
        message = cleo_engagement.otp_failure_message
        state["email_otp_sent_failed"] = True
    
    state["messages"].append(AIMessage(content=message))
    
    return state


def ask_email_otp_node(state: ChatbotState) -> ChatbotState:
    """Ask user to enter email OTP code"""
    
    print("ask_email_otp_node called")

    state["messages"].append(AIMessage(content=cleo_engagement.ask_email_otp))
    
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
                state["messages"].append(AIMessage(content="Please enter a 6-digit code (numbers only)."))
            elif error == "incorrect":
                if attempts >= 3:
                    state["messages"].append(AIMessage(content=cleo_engagement.email_otp_failure_message))
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
    
    # Check if too many attempts
    if state.get("email_otp_attempts") >= 3:
        # Reset and ask for email again
        state["email_otp_attempts"] = 0
        state["email_validation_failed"] = True
        return "ask_email"
    
    # Continue asking for OTP
    return "ask_email_otp"


# ==================== PHONE OTP VERIFICATION NODES ====================

def send_phone_otp_node(state: ChatbotState) -> ChatbotState:
    """Generate and send OTP to phone via SMS"""
    
    print("send_phone_otp_node called")
    
    phone = state["personal_details"].get("phone", "")
    
    # Generate OTP
    # otp_code = generate_otp()
    otp_code = "123456"  # For testing
    
    print("Generated phone OTP code:", otp_code)  # Debug
    # Store in state
    state["phone_otp_code"] = otp_code
    state["phone_otp_timestamp"] = time.time()
    
    # Send SMS
    # success = send_sms_otp(phone, otp_code, state.get("brand_name"))
    success = True  # For testing
    
    if success:
        message = f"I'm sending a verification text with a 6-digit code to {phone} now. Please check your messages."
        state["phone_otp_sent"] = True
    else:
        message = cleo_engagement.otp_failure_message
        state["phone_otp_sent_failed"] = True
    
    state["messages"].append(AIMessage(content=message))
    
    return state


def ask_phone_otp_node(state: ChatbotState) -> ChatbotState:
    """Ask user to enter phone OTP code"""
    
    print("ask_phone_otp_node called")
    
    state["messages"].append(AIMessage(content=cleo_engagement.ask_phone_otp))
    return state


def verify_phone_otp_node(state: ChatbotState) -> ChatbotState:
    """Verify the phone OTP code entered by user"""
    
    print("verify_phone_otp_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip()
        
        # Check for resend request
        if user_input.lower() in ["resend", "send again", "resend code"]:
            state["phone_otp_attempts"] = 0  # Reset attempts for resend
            return state
        
        # Verify OTP
        stored_code = state.get("phone_otp_code", "")
        timestamp = state.get("phone_otp_timestamp", 0)
        
        is_valid, error = verify_otp(user_input, stored_code, timestamp, "phone")
        
        if is_valid:
            state["phone_verified"] = True
            # Don't send message here - continue to next question
            state["acknowledgement_type"] = "questions"
        else:
            state["phone_otp_attempts"] += 1
            attempts = state["phone_otp_attempts"]
            
            if error == "expired":
                state["messages"].append(AIMessage(content=cleo_engagement.otp_expired_message))
                state["phone_otp_attempts"] = 0  # Reset for resend
            elif error == "invalid_format":
                state["messages"].append(AIMessage(content="Please enter a 6-digit code (numbers only)."))
            elif error == "incorrect":
                if attempts >= 3:
                    state["messages"].append(AIMessage(content=cleo_engagement.phone_otp_failure_message))
                else:
                    state["messages"].append(AIMessage(
                        content=f"The code was incorrect. I can resend the text or you can type the number again to correct any mistakes. (Attempt {attempts}/3)"
                    ))
    
    return state


def phone_otp_router(state: ChatbotState) -> Literal["acknowledgement", "send_phone_otp", "ask_phone", "ask_phone_otp", "__end__"]:
    """Route based on phone OTP verification status"""
    
    print("phone_otp_router called")

    if state.get("phone_otp_sent_failed") == True:
        print("Phone OTP not sent yet, asking for phone again.")
        return "acknowledgement"

    # Check if verified
    if state.get("phone_verified", False):
        return "acknowledgement"
    
    # Check if need to resend (expired or user requested)
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.strip().lower()
        if "resend" in user_input or "send again" in user_input:
            return "send_phone_otp"
    
    # Check if expired
    if is_otp_expired(state.get("phone_otp_timestamp", 0), "phone"):
        return "send_phone_otp"
    
    # Check if too many attempts
    if state.get("phone_otp_attempts", 0) >= 3:
        # Reset and ask for phone again
        state["phone_otp_attempts"] = 0
        state["phone_validation_failed"] = True
        return "ask_phone"
    
    # Continue asking for OTP
    return "ask_phone_otp"


# ==================== QUESTIONS LOOP ====================
def ask_question_node(state: ChatbotState) -> ChatbotState:
    """Ask screening question"""
    
    print("ask_question_node called")
    
    idx = state["current_question_index"]
    questions = state["questions"] 
    
    if idx < len(questions):
        question = questions[idx]        
        
        prompt = ASK_QUESTION_PROMPT.format(
            question=question,
            previous_question = questions[idx-1] if idx > 0 else "None",
            previous_answer = state["answers"][questions[idx-1]] if idx > 0 else "None",
            )
        
        response = llm.invoke(prompt)
        state["messages"].append(AIMessage(content=response.content))
    
    return state


def store_answer_node(state: ChatbotState) -> ChatbotState:
    """Store answer and increment index"""
    
    print("store_answer_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        idx = state["current_question_index"]
        if idx < len(state["questions"]):
            question = state["questions"][idx]
            state["answers"][question] = last_message.content
            state["current_question_index"] += 1
    
    return state


def question_router(state: ChatbotState) -> Literal["ask_question", "score"]:
    """Route to next question or scoring"""
    
    print("question_router called")
    
    if state["current_question_index"] < len(state["questions"]):
        return "ask_question"
    return "score"


# ==================== SCORING & SUMMARY ====================

def score_node(state: ChatbotState) -> ChatbotState:
    """Calculate scores"""
    
    print("score_node called")
    
    answers = state["answers"]
    scoring_model = state["scoring_model"]

    print("Answers:", answers)
    print("Scoring Model:", scoring_model)
    
    answers_str = json.dumps(answers, indent=2)
    scoring_str = json.dumps(scoring_model, indent=2)
    
    prompt = SCORING_PROMPT.format(
        answers=answers_str,
        scoring_model=scoring_str
    )
    response = llm.invoke(prompt)
    print("Scoring node response:", response.content)
    
    try:

        # Clean response (remove markdown if present)
        score_text = response.content.strip()
        if score_text.startswith("```json"):
            score_text = score_text.replace("```json", "").replace("```", "").strip()
        elif score_text.startswith("```"):
            score_text = score_text.replace("```", "").strip()
        
        result = json.loads(score_text)
        
        state["scores"] = result["scores"]
        state["score"] = result["score"]
        state["total_score"] = result.get("total_score")
        
        print("Calculated score:", result["score"])
        print("Calculated total_score:", result.get("total_score"))
    
    except json.JSONDecodeError:
        state["scores"] = {}
        state["score"] = 0
        state["total_score"] = 100
    
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
        conversation_history=conversation_history
    )
    
    return state

def end_node(state: ChatbotState) -> ChatbotState:
    """End conversation"""
    
    print("end_node called")
    
    # name = state["personal_details"].get("name")
    
    state["messages"].append(AIMessage(content=cleo_engagement.end_message))

    state["delay_node_type"] = "end"

    return state


# ==================== GRAPH BUILDER ====================

def build_graph(checkpointer):
    """Build the screening chatbot graph"""
    workflow = StateGraph(ChatbotState)
    
    # Add all nodes
    workflow.add_node("start", start_node)
    workflow.add_node("delay_messages", delay_messages_node)
    workflow.add_node("check_ready", check_ready_node)
    workflow.add_node("acknowledgement", acknowledge_node)
    
    workflow.add_node("ask_knockout_question", ask_knockout_question_node)
    workflow.add_node("store_kq_answer", store_kq_answer_node)
    
    workflow.add_node("evaluate_single_knockout", evaluate_single_knockout_node)

    workflow.add_node("ask_address", ask_address_node)
    workflow.add_node("store_address", store_address_node)
    workflow.add_node("ask_gps_verification", ask_gps_verification_node)
    workflow.add_node("process_gps", process_gps_node)
    
    workflow.add_node("ask_work_experience", ask_work_experience_node)
    workflow.add_node("store_work_experience_response", store_work_experience_response_node)
    
    workflow.add_node("ask_education", ask_education_node)
    workflow.add_node("store_education", store_education_node)
    
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
    workflow.add_node("ask_question", ask_question_node)
    workflow.add_node("store_answer", store_answer_node)
    
    workflow.add_node("score", score_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("end", end_node)
    
    # Set entry point
    workflow.set_entry_point("start")
    
    # Build flow
    workflow.add_edge("start", "delay_messages")
    workflow.add_conditional_edges("delay_messages", post_delay_router)
    
    workflow.add_conditional_edges("check_ready", ready_router)

    # Knockout Questions loop
    workflow.add_conditional_edges("acknowledgement", post_acknowledgement_router)
    
    workflow.add_edge("ask_knockout_question", "store_kq_answer")
    # workflow.add_conditional_edges("store_kq_answer", knockout_question_router)

    workflow.add_edge("store_kq_answer", "evaluate_single_knockout")

    # Route based on evaluation result
    workflow.add_conditional_edges("evaluate_single_knockout", single_knockout_router)

    # Address + GPS flow (between phone verification and questions)
    workflow.add_edge("ask_address", "store_address")
    workflow.add_edge("store_address", "ask_gps_verification")
    workflow.add_edge("ask_gps_verification", "process_gps")
    workflow.add_conditional_edges("process_gps", gps_router)
    
    # Work experience flow
    workflow.add_edge("ask_work_experience", "store_work_experience_response")
    workflow.add_edge("store_work_experience_response", "ask_education")

    # Education flow
    workflow.add_edge("ask_education", "store_education")
    workflow.add_edge("store_education", "ask_name")
    
    # Personal details flow with validation
    workflow.add_edge("ask_name", "store_name")
    workflow.add_edge("store_name", "ask_email")
    workflow.add_edge("ask_email", "store_email")
    workflow.add_conditional_edges("store_email", email_router)  # Check email validity
    
    # Email OTP verification flow
    workflow.add_conditional_edges("send_email_otp", email_otp_router)
    workflow.add_edge("ask_email_otp", "verify_email_otp")
    workflow.add_conditional_edges("verify_email_otp", email_otp_router)
    
    workflow.add_edge("ask_phone", "store_phone")
    workflow.add_conditional_edges("store_phone", phone_router)  # Check phone validity
    
    # Phone OTP verification flow
    workflow.add_conditional_edges("send_phone_otp", phone_otp_router)
    workflow.add_edge("ask_phone_otp", "verify_phone_otp")
    workflow.add_conditional_edges("verify_phone_otp", phone_otp_router)
 
    # Questions loop
    workflow.add_edge("ask_question", "store_answer")
    workflow.add_conditional_edges("store_answer", question_router)

    # Scoring and end
    workflow.add_edge("score", "summary")
    workflow.add_edge("summary", "end")
    workflow.add_edge("end", "delay_messages")
    
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["delay_messages", "ask_knockout_question",  "ask_address", "ask_gps_verification", "ask_work_experience", "store_work_experience_response", "ask_education", "ask_name", "ask_email", "ask_email_otp", "ask_phone", "ask_phone_otp", "ask_question"]
    )
    
    return app