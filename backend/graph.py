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

from otp_verification import (
    generate_otp, 
    send_email_otp, 
    send_sms_otp, 
    verify_otp,
    is_otp_expired,
    extract_email_from_text,
    extract_phone_from_text
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
    """Validate phone number (10+ digits)"""
    # Remove common separators
    cleaned = re.sub(r'[\s\-\(\)\.]', '', phone)
    # Check if it has 10+ digits
    return bool(re.match(r'^\+?\d{10,}$', cleaned))



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
    
    scoring_model: Dict[str, Dict] = {}
    scores: Dict[str, float] = {}
    total_score: float = 0
    max_possible_score: float = 0

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
    email_otp_timestamp: float = 0
    email_verified: bool = False
    email_otp_attempts: int = 0
    
    # Phone OTP fields
    phone_otp_code: str = ""
    phone_otp_timestamp: float = 0
    phone_verified: bool = False
    phone_otp_attempts: int = 0

    session_id: str = ""


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
            "Thanks for your interest — we're a friendly, locally-owned team, and I'm here to make your application process smooth and fast.",
            "I'll guide you through a quick screening. It takes less than 3 minutes in total, and we can begin whenever you're ready."
        ],
        "end": [
            "Our hiring team will take it from here. Your application will be carefully reviewed. If you are selected to move forward, we will contact you via email or phone to schedule an interview or conduct a brief background check prior to scheduling the interview.",
            f"You can expect to hear from us regarding your status within 1-2 business day. Thank you again for your time and interest in working with {state.get("brand_name")}."
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
        prompt = ASK_KNOCKOUT_QUESTION_PROMPT.format(
            question=knockout_question,
            previous_question = knockout_questions[idx-1] if idx > 0 else "None",
            previous_answer = state["knockout_answers"][knockout_questions[idx-1]] if idx > 0 else "None",
            )

        if idx == 0 or idx == 1:
            #  response = llm.invoke(prompt)
             state["messages"].append(AIMessage(content=knockout_question))
        else:
            # Use the chat template
            messages = chat_template.format_messages(user_input=prompt)
            response = llm.invoke(messages)

            prompt = prompt + "\n(Note: This is the first question.)"
    
            state["messages"].append(AIMessage(content=response.content))
    
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
            state["knockout_answers"][knockout_question] = last_message.content
            state["current_knockout_question_index"] += 1
    
    return state


def knockout_question_router(state: ChatbotState) -> Literal["ask_knockout_question", "evaluate_knockout"]:
    """Route to next knockout_question or evaluation"""
    
    print("knockout_question_router called")
    
    if state["current_knockout_question_index"] < len(state["knockout_questions"]):
        return "ask_knockout_question"
    return "evaluate_knockout"


# ==================== KNOCKOUT EVALUATION ====================

def evaluate_knockout_node(state: ChatbotState) -> ChatbotState:
    """Evaluate knockout answers using LLM"""
    
    print("evaluate_knockout_node called")
    
    knockout_questions = state["knockout_questions"]
    knockout_answers = state["knockout_answers"]
    
    # Format questions and answers for prompt
    qa_pairs = []
    for question in knockout_questions:
        answer = knockout_answers.get(question, "No answer")
        qa_pairs.append(f"Q: {question}\nA: {answer}")
    
    qa_text = "\n\n".join(qa_pairs)
    
    # Evaluate using LLM
    prompt = KNOCKOUT_EVALUATION_PROMPT.format(
        knockout_questions="",
        knockout_answers=qa_text
    )
    
    # Use chat template
    messages = chat_template.format_messages(user_input=prompt)
    response = llm.invoke(messages)
    
    # Get decision (should be "PASS" or "FAIL")
    decision = response.content.strip().upper()
    
    print(f"Knockout evaluation: {decision}")
    
    if decision == "PASS":
        state["knockout_passed"] = True
    else:
        state["knockout_passed"] = False
        failure_message = cleo_engagement.failure_message
        
        # Add failure message to conversation
        state["messages"].append(AIMessage(content=failure_message))
    
    return state


def knockout_evaluation_router(state: ChatbotState) -> Literal["ask_name", "__end__"]:
    """Route based on knockout evaluation"""
    
    print("knockout_evaluation_router called")
    
    if state.get("knockout_passed"):
        return "ask_name"  # Continue to personal details
    return "__end__"       # go directly to END




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
        if state.get("phone_attempt_count", 0) >= 3:
            # After 3 attempts, show example
            prompt = PERSONAL_DETAIL_REASK_WITH_EXAMPLE_PROMPT.format(
                detail_type="phone number",
                invalid_attempt=state.get("invalid_phone_attempt"),
                example="+1-234-567-8900 or 2345678900"
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
    else:
        message = cleo_engagement.otp_failure_message
    
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
    otp_code = generate_otp()
    # otp_code = "123456"  # For testing
    
    print("Generated phone OTP code:", otp_code)  # Debug
    # Store in state
    state["phone_otp_code"] = otp_code
    state["phone_otp_timestamp"] = time.time()
    
    # Send SMS
    success = send_sms_otp(phone, otp_code, state.get("brand_name"))
    # success = True  # For testing
    
    if success:
        message = f"I'm sending a verification text with a 6-digit code to {phone} now. Please check your messages."
    else:
        message = cleo_engagement.otp_failure_message
    
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


def phone_otp_router(state: ChatbotState) -> Literal["acknowledgement", "send_phone_otp", "ask_phone", "ask_phone_otp"]:
    """Route based on phone OTP verification status"""
    
    print("phone_otp_router called")
    
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
        state["total_score"] = result["total_score"]
        state["max_possible_score"] = result.get("max_possible_score")
        
        print("Calculated total_score:", result["total_score"])
        print("Calculated max_possible_score:", result.get("max_possible_score"))
    except json.JSONDecodeError:
        state["scores"] = {}
        state["total_score"] = 0
        state["max_possible_score"] = 100
    
    return state



def summary_node(state: ChatbotState) -> ChatbotState:
    """Generate comprehensive JSON report and send to XANO"""
    
    print("summary_node called")
    
    # Extract data from state
    name = state["personal_details"].get("name", "Candidate")
    email = state["personal_details"].get("email", "")
    phone = state["personal_details"].get("phone", "")
    session_id = state.get("session_id", "")
    
    knockout_answers = state.get("knockout_answers", {})
    answers = state.get("answers", {})
    total_score = state.get("total_score", 0)
    max_score = state.get("max_possible_score", 100)
    
    # Format knockout answers for prompt
    knockout_text = "\n".join([
        f"Q: {q}\nA: {a}" for q, a in knockout_answers.items()
    ])
    
    # Format screening answers for prompt
    answers_text = "\n".join([
        f"Q: {q}\nA: {a}" for q, a in answers.items()
    ])
    
    
    prompt = JSON_REPORT_PROMPT.format(
        name=name,
        email=email,
        phone=phone,
        session_id=session_id,
        knockout_answers=knockout_text,
        answers=answers_text,
        total_score=f"{total_score:.1f}",
        max_score=f"{max_score:.1f}"
    )
    
    print("Generating JSON report...")
    response = llm.invoke(prompt)
    
    # Parse JSON response
    try:
        # Clean response (remove markdown if present)
        json_text = response.content.strip()
        if json_text.startswith("```json"):
            json_text = json_text.replace("```json", "").replace("```", "").strip()
        elif json_text.startswith("```"):
            json_text = json_text.replace("```", "").strip()
        
        json_report = json.loads(json_text)
        print("Successfully generated below JSON report...")
        print(json_report)
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse JSON report: {e}")
        print(f"Response was: {response.content[:500]}")
        
        # Fallback: Create basic JSON structure
        json_report = create_fallback_report(
            name, email, phone, session_id, 
            knockout_answers, answers, total_score, max_score
        )
    
    # Send to XANO
    from xano import send_applicant_to_xano
    
    # job_id = state.get("job_id", "")
    
    send_applicant_to_xano(
        name=name,
        email=email,
        phone=phone,
        score=total_score,
        max_score=max_score,
        json_report=json_report,
        answers=answers,
        session_id=session_id
    )
    
    return state


def create_fallback_report(name, email, phone, session_id, knockout_answers, answers, total_score, max_score):
    """
    Create a fallback JSON report if LLM generation fails
    """
    from datetime import datetime
    
    percentage = (total_score / max_score * 100) if max_score > 0 else 0
    
    return {
        "report_metadata": {
            "session_id": session_id,
            "generated_at": datetime.now().isoformat(),
            "report_version": "1.0"
        },
        "applicant_information": {
            "full_name": name,
            "email": email,
            "phone_number": phone,
            "address": None
        },
        "qualification": {
            "requirements": [
                {
                    "criterion": q,
                    "met": True,  
                    "evidence": a,
                    "importance": "High"
                }
                for q, a in knockout_answers.items()
            ],
            "overall_qualified": True
        },
        "experiences": [
            {
                "years_experience": 0,
                "job_title": None,
                "employer": None,
                "duration": None,
                "skills": None,
                "relevant_experience": "See screening answers for details"
            }
        ],
        "education": [],
        "fit_score": {
            "total_score": int(total_score),
            "qualification_score": 100,
            "experience_score": int(percentage),
            "personality_score": 80,
            "rating": "Good" if percentage >= 60 else "Fair",
            "explanation": f"Candidate scored {total_score:.1f} out of {max_score:.1f} ({percentage:.1f}%)"
        },
        "summary": {
            "eligibility_status": "Eligible" if total_score > 50 else "Not Eligible",
            "recommendation": "Recommend for interview" if total_score > 50 else "Do not recommend",
            "key_strengths": ["Completed screening process"],
            "concerns": [] if total_score > 50 else ["Score below threshold"]
        },
        "interview_notes": {
            "notable_responses": [f"{q}: {a}" for q, a in list(answers.items())[:2]],
            "overall_impression": "Candidate completed the screening process."
        }
    }



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
    workflow.add_node("evaluate_knockout", evaluate_knockout_node)
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
    workflow.add_conditional_edges("store_kq_answer", knockout_question_router)

    #  knockout evaluation flow
    workflow.add_conditional_edges("evaluate_knockout", knockout_evaluation_router)
    
    # Personal details flow with validation
    workflow.add_edge("ask_name", "store_name")
    workflow.add_edge("store_name", "ask_email")
    workflow.add_edge("ask_email", "store_email")
    workflow.add_conditional_edges("store_email", email_router)  # Check email validity
    
    # Email OTP verification flow
    workflow.add_edge("send_email_otp", "ask_email_otp")
    workflow.add_edge("ask_email_otp", "verify_email_otp")
    workflow.add_conditional_edges("verify_email_otp", email_otp_router)
    
    workflow.add_edge("ask_phone", "store_phone")
    workflow.add_conditional_edges("store_phone", phone_router)  # Check phone validity
    
    # Phone OTP verification flow
    workflow.add_edge("send_phone_otp", "ask_phone_otp")
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
        interrupt_after=["delay_messages", "ask_knockout_question", "ask_name", "ask_email", "ask_email_otp", "ask_phone", "ask_phone_otp", "ask_question"]
    )
    
    return app