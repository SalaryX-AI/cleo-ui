"""FastAPI WebSocket server for screening chatbot"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from langchain.schema import HumanMessage, AIMessage
import json
import uuid
from graph import build_graph, ChatbotState
from job_configs import JOB_CONFIGS

from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row
import os
import asyncio


brand_name = ""

# Initialize graph at startup
graph_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_app
    
    # Get connection string
    connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("POSTGRES_CONNECTION_STRING not set")
    
    # Create async connection
    conn = await AsyncConnection.connect(
        connection_string,
        autocommit=True,
        row_factory=dict_row
    )
    
    # Create async checkpointer
    checkpointer = AsyncPostgresSaver(conn)
    await checkpointer.setup()
    
    # Build graph with checkpointer
    graph_app = build_graph(checkpointer)
    print("Graph initialized with AsyncPostgresSaver")
    
    yield
    
    # Cleanup
    await conn.close()
    print("Connection closed")

# Update FastAPI initialization
app = FastAPI(title="Screening Chatbot API", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Allowed domains list - only these domains can embed the chatbot
# Add specific production domains here
ALLOWED_DOMAINS = [
    "*",  # Wildcard allows all domains (for testing)
    "localhost",
    "127.0.0.1",
    "bigchicken.vercel.app",
    "burgerking-olive.vercel.app",
    "mcdonald-eta.vercel.app",
    "popeyes-ten.vercel.app",
    "starbucks-virid-three.vercel.app",
    "scanandhire.com"

    # "example.com",
    # "www.example.com",
]

Brand_names = {
    "bigchicken.vercel.app": "Big Chicken",
    "burgerking-olive.vercel.app": "Burger King",
    "mcdonald.vercel.app": "McDonald's",
    "popeyes.vercel.app": "Popeyes",
    "starbucks.vercel.app": "Starbucks",
    "127.0.0.1": "Big Chicken",
    "scanandhire.com": "Big Chicken",
}

# API key for authenticated requests
API_KEY = "test_key_secure_123"

# Store active sessions
sessions = {}

@app.get("/")
async def root():
    """Serve test page"""
    with open("./client-websites/big_chicken_frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/cleoAssistant.js")
async def serve_embed_script():
    """Serve the chatbot embed script"""
    return FileResponse("cleoAssistant.js", media_type="application/javascript")


@app.get("/validate-domain")
async def validate_domain(
    domain: str = Query(..., description="Domain where chatbot is embedded")
):
    """
    Validate domain and return API key if authorized.
    
    This endpoint:
    1. Validates the domain against ALLOWED_DOMAINS list
    2. Returns the API key if domain is authorized
    
    Job type validation happens when session is created.
    """
    
    # Validate domain against ALLOWED_DOMAINS list
    if "*" not in ALLOWED_DOMAINS:
        # Strict domain checking
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(
                status_code=403,
                detail=f"Domain '{domain}' is not authorized"
            )
    
    global brand_name
    brand_name = Brand_names.get(domain, "")

    # Return API key if validation passes
    return {
        "apiKey": API_KEY
    }


@app.post("/start-session")
async def start_session(job_type: str = Query(...), api_key: str = Query(...), location: str = Query(...)):
    """Create new screening session for a specific job type"""
    
    # Validate job_type exists
    if job_type not in JOB_CONFIGS:
        raise HTTPException(status_code=404, detail="Job type not found")
    
    # Validate API key
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    # Create session
    session_id = str(uuid.uuid4())
    thread_id = f"thread_{job_type}_{session_id}"
    
    sessions[session_id] = {
        "thread_id": thread_id,
        "job_type": job_type,
        "location": location,
        "active": True
    }
    
    return {
        "session_id": session_id,
        "job_type": job_type,
        "position": job_type.replace('_', ' ').title()
    }


def set_job_address(job_config: dict, location: str):

    # Replace placeholder in knockout questions
    job = job_config.copy()
    job["knockout_questions"] = [
        q.format(address=location) for q in job["knockout_questions"]
    ]

    print(f"Updated Job ->: {job}")

    return job

@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket connection for chat"""
    await websocket.accept()
    
    if session_id not in sessions:
        await websocket.send_json({
            "type": "error",
            "message": "Invalid session ID"
        })
        await websocket.close()
        return
    
    session = sessions[session_id]
    thread_id = session["thread_id"]
    job_type = session["job_type"]
    location = session["location"]
    job_config = JOB_CONFIGS[job_type]

    job = set_job_address(job_config, location)


    global brand_name
    
    # graph_app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        initial_state = ChatbotState(
            messages=[],
            questions=job["questions"],
            scoring_model=job["scoring_model"],
            current_question_index=0,
            answers={},
            personal_details={},
            ready_confirmed=False,
            knockout_answers={},
            current_knockout_question_index=0,
            knockout_questions=job["knockout_questions"],
            
            email_attempt_count=0,
            phone_attempt_count=0,
            email_validation_failed=False,
            phone_validation_failed=False,
            invalid_email_attempt="",
            invalid_phone_attempt="",
            acknowledgement_type="",
            
            delay_node_type="",
            
            knockout_passed=False,
            brand_name=brand_name,

            email_otp_code="",
            email_otp_timestamp=0,
            email_verified=False,
            email_otp_attempts=0,
            phone_otp_code="",
            phone_otp_timestamp=0,
            phone_verified=False,
            phone_otp_attempts=0
        )
        
        async for event in graph_app.astream(initial_state, config=config, stream_mode="updates"):
            for node_name, node_data in event.items():
                if node_data and "messages" in node_data:
                    messages = node_data["messages"]
                    
                    # Check if this is delay_messages_node
                    if node_name == "delay_messages":
                        
                        await asyncio.sleep(2)  # Initial delay before starting
                        
                        for msg in messages[-2:]:   # only last two messages
                            print(msg.content)
                            if isinstance(msg, AIMessage):
                                await websocket.send_json({
                                    "type": "ai_message",
                                    "content": msg.content
                                })
                                await asyncio.sleep(2)  # 1 second delay
                    else:
                        # Normal processing - send last message only
                        msg = messages[-1]
                        print(msg.content)
                        if isinstance(msg, AIMessage):
                            await websocket.send_json({
                                "type": "ai_message",
                                "content": msg.content
                            })
        
        while True:
            
            # Check if workflow completed
            snapshot = await graph_app.aget_state(config)
            if not snapshot.next:
                await websocket.send_json({
                    "type": "workflow_complete",
                })
                break
            
            data = await websocket.receive_text()
            message_data = json.loads(data)
            
            if message_data.get("type") != "user_message":
                continue
            
            user_input = message_data.get("content", "").strip()
            if not user_input:
                continue
            
            current_state = await graph_app.aget_state(config)
            current_messages = current_state.values.get("messages", [])
            
            await graph_app.aupdate_state(
                config,
                {"messages": current_messages + [HumanMessage(content=user_input)]}
            )
            
            # Resume workflow with streaming
            async for event in graph_app.astream(None, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    if node_data and "messages" in node_data:
                        messages = node_data["messages"]
                        
                        # Check if this is delay_messages_node
                        if node_name == "delay_messages":
                            print("Processing delay_messages node")
                            await asyncio.sleep(3)  # Initial delay before starting
                            
                            for msg in messages[-2:]:   # only last two messages
                                print(msg.content)
                                if isinstance(msg, AIMessage):
                                    await websocket.send_json({
                                        "type": "ai_message",
                                        "content": msg.content
                                    })
                                    await asyncio.sleep(3)  # 3 second delay
                        else:
                            # Normal processing - send last message only
                            msg = messages[-1]
                            print(msg.content)
                            if isinstance(msg, AIMessage):
                                await websocket.send_json({
                                    "type": "ai_message",
                                    "content": msg.content
                                })
    
    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
        sessions[session_id]["active"] = False
    
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()  # Get full error trace
        print(f"Error in WebSocket: {e}")
        print(f"Full traceback:\n{error_details}")  # NEW - shows full error
        await websocket.send_json({
            "type": "error",
            "message": str(e)
        })
        await websocket.close()


if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)