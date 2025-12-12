"""Main graph implementation for Cleo screening chatbot with human-in-the-loop"""

import json
from typing import Literal, List, Dict
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
    is_otp_expired
)
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
    personal_details: Dict[str, str] = {}
    ready_confirmed: bool = False
    scores: Dict[str, float] = {}
    total_score: float = 0
    max_possible_score: float = 0

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


# ==================== Acknowledgement ====================
def acknowledge_node(state: ChatbotState) -> ChatbotState:
    """Send acknowledgment message"""
    print(f"acknowledge_node called (type: {state['acknowledgement_type']})")

    ack_messages = {
        "ready": "Ok! I'll guide you through each step. You can stop or come back anytime. Let's start!",
        "questions": "Thanks! For sharing your contact details with us. Now we are moving on next stage. Let's start!",
        "default": "Let's continue!"
    }

    ack_type = state.get("acknowledgement_type", "default")
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
            "We're a friendly, locally-owned team here. My job is to make your application process super fast and easy.",
            "I just need to ask a few quick screening questions, it'll take less than 2 minutes total. Ready to jump in?"
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
    
    # prompt = GREETING_PROMPT.format()

    # Use the chat template
    # messages = chat_template.format_messages(user_input=prompt)
    # response = llm.invoke(prompt)
    
    state["messages"].append(AIMessage(content=f"Hello. I'm Cleo, the hiring assistant for {state['brand_name']}. Thank you for your interest in this role."))

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
            decline_message = "No problem at all! Thanks for stopping by. Feel free to reach out anytime. Take care!"
            state["messages"].append(AIMessage(content=decline_message))    
    
    return state


def ready_router(state: ChatbotState) -> Literal["acknowledgement", "__end__"]:
    """Route based on ready confirmation"""
    
    print("ready_router called")
    
    if state["ready_confirmed"]:
        return "acknowledgement"
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
        
        # Use the chat template
        messages = chat_template.format_messages(user_input=prompt)
        response = llm.invoke(messages)
            
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
        failure_messages = "Thank you for your interest! Unfortunately, based on your responses, you don't meet our basic requirements at this time. We appreciate you taking the time to chat with us. Best of luck in your job search!"
        
        # Add failure message to conversation
        state["messages"].append(AIMessage(content=failure_messages))
    
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

    prompt = PERSONAL_DETAIL_ASK_PROMPT.format(
        detail_type="name",
        previous_question="None",
        previous_answer="None",
    )
    
    # Use the chat template
    messages = chat_template.format_messages(user_input=prompt)
    response = llm.invoke(messages)
        
    state["messages"].append(AIMessage(content=response.content))
    
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
        email = last_message.content.strip()
        
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
        else:
            # Normal re-ask (no example)
            prompt = PERSONAL_DETAIL_REASK_PROMPT.format(
                detail_type="phone number",
                invalid_attempt=state.get("invalid_phone_attempt")
            )
    else:
        # Use normal ask prompt
        prompt = PERSONAL_DETAIL_ASK_PROMPT.format(
            detail_type="phone number",
            previous_question="What is your email address?",
            previous_answer=state["personal_details"].get("email", "None")
        )

    # Use the chat template
    messages = chat_template.format_messages(user_input=prompt)
    response = llm.invoke(messages)
    
    state["messages"].append(AIMessage(content=response.content))
    
    return state


def store_phone_node(state: ChatbotState) -> ChatbotState:
    """Store phone from user input with validation"""
    
    print("store_phone_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        phone = last_message.content.strip()
        
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
    
    # Store in state
    state["email_otp_code"] = otp_code
    state["email_otp_timestamp"] = time.time()
    brand_name = state.get("brand_name")
    
    # Send email
    success = send_email_otp(email, otp_code, brand_name, user_name)
    
    if success:
        message = f"Okay, I've just sent a 6-digit verification code to {email}. Please check your inbox (and spam folder)"
    else:
        message = "I'm having trouble sending the verification email right now. Let me try again in a moment."
    
    state["messages"].append(AIMessage(content=message))
    
    return state


def ask_email_otp_node(state: ChatbotState) -> ChatbotState:
    """Ask user to enter email OTP code"""
    
    print("ask_email_otp_node called")
    
    # Check if we need to resend
    # if state.get("email_otp_attempts", 0) > 0:
    #     message = "Please enter the 6-digit code from your email:"
    #     state["messages"].append(AIMessage(content=message))

    state["messages"].append(AIMessage(content="Please enter the 6-digit code from your email:"))    
    
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
        
        is_valid, error = verify_otp(user_input, stored_code, timestamp)
        
        if is_valid:
            state["email_verified"] = True
            state["messages"].append(AIMessage(content="Success! Your email address is confirmed."))
        else:
            state["email_otp_attempts"] += 1
            attempts = state["email_otp_attempts"]
            
            if error == "expired":
                state["messages"].append(AIMessage(
                    content="That code has expired. Let me send you a fresh one."
                ))
                state["email_otp_attempts"] = 0  # Reset for resend
            elif error == "invalid_format":
                state["messages"].append(AIMessage(
                    content="Please enter a 6-digit code (numbers only)."
                ))
            elif error == "incorrect":
                if attempts >= 3:
                    state["messages"].append(AIMessage(
                        content="Hmm, that code didn't work after 3 tries. Let's start over with your email address."
                    ))
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
    if is_otp_expired(state.get("email_otp_timestamp", 0)):
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
    
    # Store in state
    state["phone_otp_code"] = otp_code
    state["phone_otp_timestamp"] = time.time()
    
    # Send SMS
    success = send_sms_otp(phone, otp_code, state.get("brand_name"))
    
    if success:
        message = f"I'm sending a verification text with a 6-digit code to {phone} now. Please check your messages."
    else:
        message = "I'm having trouble sending the verification text right now. Let me try again in a moment."
    
    state["messages"].append(AIMessage(content=message))
    
    return state


def ask_phone_otp_node(state: ChatbotState) -> ChatbotState:
    """Ask user to enter phone OTP code"""
    
    print("ask_phone_otp_node called")
    
    # Check if we need to resend
    # if state.get("phone_otp_attempts", 0) > 0:
    #     message = "Please enter the 6-digit code from your text message:"
    #     state["messages"].append(AIMessage(content=message))
    
    state["messages"].append(AIMessage(content="Please enter the 6-digit code from your text message:"))
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
        
        is_valid, error = verify_otp(user_input, stored_code, timestamp)
        
        if is_valid:
            state["phone_verified"] = True
            # Don't send message here - continue to next question
            state["acknowledgement_type"] = "questions"
        else:
            state["phone_otp_attempts"] += 1
            attempts = state["phone_otp_attempts"]
            
            if error == "expired":
                state["messages"].append(AIMessage(
                    content="That code has expired. Let me send you a fresh one."
                ))
                state["phone_otp_attempts"] = 0  # Reset for resend
            elif error == "invalid_format":
                state["messages"].append(AIMessage(
                    content="Please enter a 6-digit code (numbers only)."
                ))
            elif error == "incorrect":
                if attempts >= 3:
                    state["messages"].append(AIMessage(
                        content="The code was incorrect after 3 tries. Let's start over with your phone number."
                    ))
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
    if is_otp_expired(state.get("phone_otp_timestamp", 0)):
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
        result = json.loads(response.content)
        state["scores"] = result["scores"]
        state["total_score"] = result["total_score"]
        state["max_possible_score"] = result.get("max_possible_score", 100)
    except json.JSONDecodeError:
        state["scores"] = {}
        state["total_score"] = 0
        state["max_possible_score"] = 100
    
    return state


def summary_node(state: ChatbotState) -> ChatbotState:
    """Generate summary"""
    
    print("summary_node called")
    
    name = state["personal_details"].get("name", "Candidate")
    answers = state["answers"]
    total_score = state["total_score"]
    max_score = state["max_possible_score"]
    
    answers_text = "\n".join([f"- {q}: {a}" for q, a in answers.items()])
    
    prompt = SUMMARY_PROMPT.format(
        name=name,
        answers=answers_text,
        total_score=f"{total_score:.1f}",
        max_score=f"{max_score:.1f}"
    )
    response = llm.invoke(prompt)
    state["messages"].append(AIMessage(content=response.content))
    
    return state


def end_node(state: ChatbotState) -> ChatbotState:
    """End conversation"""
    
    print("end_node called")
    
    name = state["personal_details"].get("name", "")
    
    # prompt = END_PROMPT.format(name=name)
    
    # response = llm.invoke(prompt)
    
    state["messages"].append(AIMessage(content=f"Great Job {name}! You've successfully completed the initial application. Your information has been securely saved and submitted."))

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
    # workflow.add_node("summary", summary_node)
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
    workflow.add_edge("score", "end")
    workflow.add_edge("end", "delay_messages")
    
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["delay_messages", "ask_knockout_question", "ask_name", "ask_email", "ask_email_otp", "ask_phone", "ask_phone_otp", "ask_question"]
    )
    
    return app