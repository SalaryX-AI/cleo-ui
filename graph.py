"""Main graph implementation for Cleo screening chatbot with human-in-the-loop"""

import json
from typing import TypedDict, Literal, List, Dict
from langgraph.graph import StateGraph, END, MessagesState
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage, AIMessage
from prompts_improved import *
import os
from dotenv import load_dotenv

load_dotenv()
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)


class ChatbotState(MessagesState):
    """State for the screening chatbot"""
    current_question_index: int = 0
    questions: List[str] = []
    answers: Dict[str, str] = {}
    scoring_model: Dict[str, Dict] = {}
    personal_details: Dict[str, str] = {}
    ready_confirmed: bool = False
    scores: Dict[str, float] = {}
    total_score: float = 0
    max_possible_score: float = 0


# ==================== START & READY FLOW ====================

def start_node(state: ChatbotState) -> ChatbotState:
    """Send greeting and ask if ready"""

    print("start_node called")
    
    prompt = GREETING_PROMPT.format()
    response = llm.invoke(prompt)
    # print(response.content)
    
    state["messages"].append(AIMessage(content=response.content))
    
    return state


def check_ready_node(state: ChatbotState) -> ChatbotState:
    """Process ready response"""

    print("check_ready_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        user_input = last_message.content.lower().strip()
        if "yes" in user_input or "accept" in user_input or "ready" in user_input:
            state["ready_confirmed"] = True
    
    return state


def ready_router(state: ChatbotState) -> Literal["ask_name", "end"]:
    """Route based on ready confirmation"""
    
    print("ready_router called")
    
    if state["ready_confirmed"]:
        return "ask_name"
    return "end"


# ==================== PERSONAL DETAILS COLLECTION ====================

def ask_name_node(state: ChatbotState) -> ChatbotState:
    """Ask for name"""
    
    print("ask_name_node called")
    
    prompt = PERSONAL_DETAIL_PROMPT.format(
        detail_type="name",
        previous_answer="None"
    )
    response = llm.invoke(prompt)
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


def ask_email_node(state: ChatbotState) -> ChatbotState:
    """Ask for email"""
    
    print("ask_email_node called")
    
    prompt = PERSONAL_DETAIL_PROMPT.format(
        detail_type="email",
        previous_answer=state["personal_details"].get("name", "")
    )
    response = llm.invoke(prompt)
    state["messages"].append(AIMessage(content=response.content))
    
    return state


def store_email_node(state: ChatbotState) -> ChatbotState:
    """Store email from user input"""
    
    print("store_email_node called")

    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        state["personal_details"]["email"] = last_message.content
    
    return state


def ask_phone_node(state: ChatbotState) -> ChatbotState:
    """Ask for phone"""
    
    print("ask_phone_node called")
    
    prompt = PERSONAL_DETAIL_PROMPT.format(
        detail_type="phone",
        previous_answer=state["personal_details"].get("email", "")
    )
    response = llm.invoke(prompt)
    state["messages"].append(AIMessage(content=response.content))
    
    return state


def store_phone_node(state: ChatbotState) -> ChatbotState:
    """Store phone from user input"""
    
    print("store_phone_node called")
    
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, HumanMessage):
        state["personal_details"]["phone"] = last_message.content
    
    return state


# ==================== QUESTIONS LOOP ====================

def ask_question_node(state: ChatbotState) -> ChatbotState:
    """Ask screening question"""
    
    print("ask_question_node called")
    
    idx = state["current_question_index"]
    questions = state["questions"]
    
    if idx < len(questions):
        question = questions[idx]
        prompt = ASK_QUESTION_PROMPT.format(question=question)
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
    prompt = END_PROMPT.format(name=name)
    response = llm.invoke(prompt)
    state["messages"].append(AIMessage(content=response.content))
    return state


# ==================== GRAPH BUILDER ====================

def build_graph():
    """Build the screening chatbot graph"""
    workflow = StateGraph(ChatbotState)
    
    # Add all nodes
    workflow.add_node("start", start_node)
    workflow.add_node("check_ready", check_ready_node)
    workflow.add_node("ask_name", ask_name_node)
    workflow.add_node("store_name", store_name_node)
    workflow.add_node("ask_email", ask_email_node)
    workflow.add_node("store_email", store_email_node)
    workflow.add_node("ask_phone", ask_phone_node)
    workflow.add_node("store_phone", store_phone_node)
    workflow.add_node("ask_question", ask_question_node)
    workflow.add_node("store_answer", store_answer_node)
    workflow.add_node("score", score_node)
    workflow.add_node("summary", summary_node)
    workflow.add_node("end", end_node)
    
    # Set entry point
    workflow.set_entry_point("start")
    
    # Build flow
    workflow.add_edge("start", "check_ready")
    workflow.add_conditional_edges("check_ready", ready_router)
    
    # Personal details flow
    workflow.add_edge("ask_name", "store_name")
    workflow.add_edge("store_name", "ask_email")
    workflow.add_edge("ask_email", "store_email")
    workflow.add_edge("store_email", "ask_phone")
    workflow.add_edge("ask_phone", "store_phone")
    workflow.add_edge("store_phone", "ask_question")
    
    # Questions loop
    workflow.add_edge("ask_question", "store_answer")
    workflow.add_conditional_edges("store_answer", question_router)
    
    # Scoring and end
    workflow.add_edge("score", "summary")
    workflow.add_edge("summary", END)
    # workflow.add_edge("end", END)
    
    # Compile with memory
    memory = MemorySaver()
    app = workflow.compile(
        checkpointer=memory,
        interrupt_after=["start", "ask_name", "ask_email", "ask_phone", "ask_question"]
    )
    
    return app


# ==================== CLI INTERACTION ====================

def run_cli_chat():
    """Run chatbot with CLI interaction"""
    
    questions_json = {
        "questions": [
            "What is your age?",
            "Do you have experience in software testing?",
            "How many months of experience do you have?"
        ],
        "scoring_model": {
            "What is your age?": {"rule": "Must be >= 18", "score": 1},
            "Do you have experience in software testing?": {"rule": "Yes -> 5, No -> 0"},
            "How many months of experience do you have?": {"rule": "Score = months / 2"}
        }
    }
    
    app = build_graph()
    config = {"configurable": {"thread_id": "cli_session1"}}
    
    state = ChatbotState(
        messages=[],
        questions=questions_json["questions"],
        scoring_model=questions_json["scoring_model"],
        current_question_index=0,
        answers={},
        personal_details={},
        ready_confirmed=False
    )
    
    print("=" * 50)
    print("SCREENING CHATBOT")
    print("=" * 50)
    
    # Start workflow
    result = app.invoke(state, config=config)
    
    # Show AI message
    if result.get("messages"):
        last_msg = result["messages"][-1]
        if isinstance(last_msg, AIMessage):
            print(f"\n🤖 Cleo: {last_msg.content}")
    
    # Main loop
    while True:
        print("in the loop")
        snapshot = app.get_state(config)
        
        if not snapshot.next:
            print("\n" + "=" * 50)
            print("CONVERSATION ENDED")
            print("=" * 50)
            break
        
        user_input = input("\n👤 You: ").strip()
        if not user_input:
            continue
        
        # SAFEST: Update state, then resume
        current_state = app.get_state(config)
        current_messages = current_state.values.get("messages", [])
        
        app.update_state(
            config,
            {"messages": current_messages + [HumanMessage(content=user_input)]}
        )
        
        # Resume from checkpoint (don't pass input)
        result = app.invoke(None, config=config)
        
        # Show AI response
        if result.get("messages"):
            last_msg = result["messages"][-1]
            if isinstance(last_msg, AIMessage):
                print(f"\n🤖 Bot: {last_msg.content}")



if __name__ == "__main__":
    run_cli_chat()