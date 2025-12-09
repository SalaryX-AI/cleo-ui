"""Main graph implementation for Cleo screening chatbot with human-in-the-loop"""

import json
from typing import TypedDict, Literal, List, Dict
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.types import Command, interrupt
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from prompts1 import *
import os
from dotenv import load_dotenv
from langchain.prompts import ChatPromptTemplate
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
            "I just need to ask a few quick screening questions—it'll take less than 2 minutes total. Ready to jump in?"
        ],
        "end": [
            "Our hiring team will take it from here. Your application will be carefully reviewed. If you are selected to move forward, we will contact you via email or phone to schedule an interview or conduct a brief background check prior to scheduling the interview.",
            "You can expect to hear from us regarding your status within 1-2 business day. Thank you again for your time and interest in working with Big Chicken!."
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


def email_router(state: ChatbotState) -> Literal["ask_email", "ask_phone"]:
    """Check if email is valid, re-ask or continue"""
    
    print("email_router called")
    
    if state.get("email_validation_failed", False):
        return "ask_email"  # Re-ask for email
    return "ask_phone"  # Continue to phone


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


def phone_router(state: ChatbotState) -> Literal["ask_phone", "acknowledgement"]:
    """Check if phone is valid, re-ask or continue"""
    
    print("phone_router called")
    
    if state.get("phone_validation_failed", False):
        return "ask_phone"  # Re-ask for phone
    
    return "acknowledgement"  # Continue to questions


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
    workflow.add_node("ask_phone", ask_phone_node)
    workflow.add_node("store_phone", store_phone_node)
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
    
    workflow.add_edge("ask_phone", "store_phone")
    workflow.add_conditional_edges("store_phone", phone_router)  # Check phone validity
 
    # Questions loop
    workflow.add_edge("ask_question", "store_answer")
    workflow.add_conditional_edges("store_answer", question_router)

    # Scoring and end
    workflow.add_edge("score", "end")
    workflow.add_edge("end", "delay_messages")
    
    app = workflow.compile(
        checkpointer=checkpointer,
        interrupt_after=["delay_messages", "ask_knockout_question", "ask_name", "ask_email", "ask_phone", "ask_question"]
    )
    
    return app