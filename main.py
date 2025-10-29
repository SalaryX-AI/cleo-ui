"""FastAPI WebSocket server for screening chatbot"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from langchain.schema import HumanMessage, AIMessage
import json
import uuid
from graph import build_graph, ChatbotState
from xano import get_job_details_by_id

app = FastAPI(title="Screening Chatbot API")

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store active sessions
sessions = {}

# Questions config
# QUESTIONS_CONFIG = {
#     "questions": [
#         "What is your age?",
#         "Do you have experience in software testing?",
#         "How many months of experience do you have?"
#     ],
#     "scoring_model": {
#         "What is your age?": {"rule": "Must be >= 18", "score": 1},
#         "Do you have experience in software testing?": {"rule": "Yes -> 5, No -> 0"},
#         "How many months of experience do you have?": {"rule": "Score = months / 2"}
#     }
# }

QUESTIONS_CONFIG = {
  "questions": [
    "Do you have interest in a part-time job role?",
    "Are you available for morning shifts?",
    "Can you start working from October 17, 2025?",
    "Can you confirm you are aged 18 and above?",
    "Can you consent for a background check to be conducted?",
    "Are you comfortable if a uniform is to be worn during work hours?",
    "Do you have a minimum of 4 years of experience in a field related to this job?"
  ],
  "scoring_model": {
    "Do you have interest in a part-time job role?": {"rule": "Yes -> 10, No -> 0"},
    "Are you available for morning shifts?": {"rule": "Yes -> 10, No -> 0"},
    "Can you start working from October 17, 2025?": {"rule": "Yes -> 10, No -> 0"},
    "Can you confirm you are aged 18 and above?": {"rule": "Yes -> 10, No -> 0"},
    "Can you consent for a background check to be conducted?": {"rule": "Yes -> 10, No -> 0"},
    "Are you comfortable if a uniform is to be worn during work hours?": {"rule": "Yes -> 10, No -> 0"},
    "Do you have a minimum of 4 years of experience in a field related to this job?": {"rule": "Yes -> 40, No -> 0"}
  }
}



# QUESTIONS_CONFIG = get_job_details_by_id("ea24d345-206d-4656-936f-588aa0ecc0c2")

# QUESTIONS_CONFIG = {}

@app.get("/")
async def root():
    """Health check"""
    return {"status": "ok", "message": "Screening Chatbot API"}


@app.post("/start-session")
async def start_session():
    """Create new screening session"""
    session_id = str(uuid.uuid4())
    thread_id = f"thread_{session_id}"
    
    sessions[session_id] = {
        "thread_id": thread_id,
        "active": True
    }

    # global QUESTIONS_CONFIG 
    # QUESTIONS_CONFIG = get_job_details_by_id("ea24d345-206d-4656-936f-588aa0ecc0c2")
    
    return {
        "session_id": session_id,
        "message": "Session created"
    }


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket connection for chat"""
    await websocket.accept()
    
    # Validate session
    if session_id not in sessions:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid session ID"
        })
        await websocket.close()
        return
    
    thread_id = sessions[session_id]["thread_id"]
    graph_app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        # Initialize workflow
        initial_state = ChatbotState(
            messages=[],
            questions=QUESTIONS_CONFIG["questions"],
            scoring_model=QUESTIONS_CONFIG["scoring_model"],
            current_question_index=0,
            answers={},
            personal_details={},
            ready_confirmed=False,
            knockout_answers={},
            current_knockout_question_index=0,
            knockout_questions=["Good. Are you legally authorized to work in the U.S.?",
                                "Got it. Do you have reliable transportation to and from work?"],

            email_attempt_count=0,
            phone_attempt_count=0,
            email_validation_failed=False,
            phone_validation_failed=False,
            invalid_email_attempt="",
            invalid_phone_attempt="",
            acknowledgement_type=""                    
        )
        
        # Start workflow with streaming
        async for event in graph_app.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_data in event.items():
                if node_data and "messages" in node_data:
                    messages = node_data["messages"]
                    
                    msg = messages[-1]
                    print(msg)
                    if isinstance(msg, AIMessage):
                        await websocket.send_json({
                            "type": "ai_message",
                            "content": msg.content
                        
                    })
        
        # Main conversation loop
        while True:
            # Check if workflow completed
            # snapshot = graph_app.get_state(config)
            # if not snapshot.next:
            #     result = snapshot.values
            #     await websocket.send_json({
            #         "type": "workflow_complete",
            #         "summary": {
            #             "name": result.get("personal_details", {}).get("name", ""),
            #             "total_score": result.get("total_score", 0),
            #             "max_score": result.get("max_possible_score", 10)
            #         }
            #     })
            #     break


            # Check if workflow completed
            snapshot = graph_app.get_state(config)
            if not snapshot.next:
                break
            
            # Wait for user message
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") != "user_message":
                continue
            
            user_input = message_data.get("content", "").strip()
            if not user_input:
                continue
            
            # Update state with user message
            current_state = graph_app.get_state(config)
            current_messages = current_state.values.get("messages", [])
            
            graph_app.update_state(
                config,
                {"messages": current_messages + [HumanMessage(content=user_input)]}
            )
            
            # Resume workflow with streaming
            async for event in graph_app.astream(None, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    if node_data and "messages" in node_data:
                        messages = node_data["messages"]
                        msg = messages[-1]
                        print(msg)
                        if isinstance(msg, AIMessage):
                            await websocket.send_json({
                                "type": "ai_message",
                                "content": msg.content
                            })
    
    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
        sessions[session_id]["active"] = False
    
    except Exception as e:
        print(f"Error in WebSocket: {e}")
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        await websocket.close()


@app.get("/session/{session_id}/status")
async def get_session_status(session_id: str):
    """Get session status"""
    if session_id not in sessions:
        return {"error": "Session not found"}
    
    return {
        "session_id": session_id,
        "active": sessions[session_id]["active"]
    }


if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)