"""FastAPI WebSocket server for screening chatbot"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from langchain.schema import HumanMessage, AIMessage
import json
import uuid
from graph import build_graph, ChatbotState

app = FastAPI(title="Screening Chatbot API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Job configurations (In production, store this in a real database)
# Each job has:
# - api_key: Secret key for API authentication
# - allowed_domains: List of domains authorized to embed this chatbot ("*" for all)
# - Other job-specific configuration
JOB_CONFIGS = {
    "job_123": {
        "client_id": "client_abc",
        "company_name": "Acme Corp",
        "position": "Warehouse Worker",
        "api_key": "test_key_123",
        "allowed_domains": ["*"],  # "*" means all domains, or specify: ["example.com", "localhost"]
        "knockout_questions": [
            "Are you legally authorized to work in the U.S.?",
            "Do you have reliable transportation to work?"
        ],
        "questions": [
            "What is your age?",
            "Do you have experience in warehouse operations?",
            "How many months of warehouse experience do you have?"
        ],
        "scoring_model": {
            "What is your age?": {"rule": "Must be >= 18", "score": 1},
            "Do you have experience in warehouse operations?": {"rule": "Yes -> 5, No -> 0"},
            "How many months of warehouse experience do you have?": {"rule": "Score = months / 2"}
        }
    },
    "job_456": {
        "client_id": "client_xyz",
        "company_name": "TechStart Inc",
        "position": "Delivery Driver",
        "api_key": "test_key_456",
        "allowed_domains": ["specific-domain.com", "localhost"],  # Only these domains allowed
        "knockout_questions": [
            "Are you available to work weekends?",
            "Do you have a valid driver's license?"
        ],
        "questions": [
            "How many years of driving experience do you have?",
            "Are you comfortable with long-distance routes?"
        ],
        "scoring_model": {
            "How many years of driving experience do you have?": {"rule": "Score = years * 3"},
            "Are you comfortable with long-distance routes?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "job_789": {
        "client_id": "client_foods",
        "company_name": "Gourmet Kitchens Ltd",
        "position": "Professional Cook",
        "api_key": "test_key_789",
        "allowed_domains": ["*"],  # All domains allowed
        "knockout_questions": [
            "Do you have a valid food handler's certification?",
            "Are you available to work evenings and weekends?"
        ],
        "questions": [
            "How many years of professional cooking experience do you have?",
            "Have you worked in a commercial kitchen before?",
            "What cuisines are you most experienced with?"
        ],
        "scoring_model": {
            "How many years of professional cooking experience do you have?": {"rule": "Score = years * 3"},
            "Have you worked in a commercial kitchen before?": {"rule": "Yes -> 5, No -> 0"},
            "What cuisines are you most experienced with?": {"rule": "Each cuisine listed -> +2 points"}
        }
    }
}


# Store active sessions
sessions = {}


@app.get("/")
async def root():
    """Serve test page"""
    with open("frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/cleoAssistant.js")
async def serve_embed_script():
    """Serve the chatbot embed script"""
    return FileResponse("cleoAssistant.js", media_type="application/javascript")


@app.get("/job/{job_id}")
async def get_job_info(job_id: str):
    """Get public job information"""
    if job_id not in JOB_CONFIGS:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job = JOB_CONFIGS[job_id]
    return {
        "job_id": job_id,
        "company_name": job["company_name"],
        "position": job["position"]
}


@app.get("/validate-job")
async def validate_job(
    job_id: str = Query(..., description="Job ID to validate"),
    domain: str = Query(..., description="Domain where chatbot is embedded")
):
    """
    Validate job_id and domain, return API key if authorized.
    
    1. Checks if the job_id exists in the system
    2. Validates the domain is allowed for this job
    3. Returns the API key securely if validation passes
    
    This keeps the API key secure on the server until the client proves
    they have a valid job_id and are on an authorized domain.
    """
    
    # Check if job exists
    if job_id not in JOB_CONFIGS:
        raise HTTPException(
            status_code=404,
            detail=f"Job '{job_id}' not found"
        )
    
    job_config = JOB_CONFIGS[job_id]
    
    # Validate domain (security measure)
    allowed_domains = job_config.get("allowed_domains", ["*"])
    
    # If not wildcard, check if domain is in allowed list
    if "*" not in allowed_domains:
        if domain not in allowed_domains:
            raise HTTPException(
                status_code=403,
                detail=f"Domain '{domain}' is not authorized for this job"
            )
    
    # Return validated configuration
    return {
        "jobId": job_id,
        "apiKey": job_config["api_key"],
        "companyName": job_config.get("company_name", "Company"),
        "position": job_config.get("position", "Position")
    }


@app.post("/start-session")
async def start_session(job_id: str = Query(...), api_key: str = Query(...)):
    """Create new screening session for a specific job"""
    
    if job_id not in JOB_CONFIGS:
        raise HTTPException(status_code=404, detail="Job not found")
    
    job_config = JOB_CONFIGS[job_id]
    if job_config["api_key"] != api_key:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    session_id = str(uuid.uuid4())
    thread_id = f"thread_{job_id}_{session_id}"
    
    sessions[session_id] = {
        "thread_id": thread_id,
        "job_id": job_id,
        "client_id": job_config["client_id"],
        "active": True
    }
    
    return {
        "session_id": session_id,
        "job_id": job_id,
        "company_name": job_config["company_name"],
        "position": job_config["position"]
    }


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
    job_id = session["job_id"]
    job_config = JOB_CONFIGS[job_id]
    
    graph_app = build_graph()
    config = {"configurable": {"thread_id": thread_id}}
    
    try:
        initial_state = ChatbotState(
            messages=[],
            questions=job_config["questions"],
            scoring_model=job_config["scoring_model"],
            current_question_index=0,
            answers={},
            personal_details={},
            ready_confirmed=False,
            knockout_answers={},
            current_knockout_question_index=0,
            knockout_questions=job_config["knockout_questions"],
            
            email_attempt_count=0,
            phone_attempt_count=0,
            email_validation_failed=False,
            phone_validation_failed=False,
            invalid_email_attempt="",
            invalid_phone_attempt="",
            acknowledgement_type="",
            knockout_passed=False,
        )
        
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
        
        while True:
            # snapshot = graph_app.get_state(config)
            # if not snapshot.next:
            #     result = snapshot.values
            #     await websocket.send_json({
            #         "type": "workflow_complete",
            #         "summary": {
            #             "name": result.get("personal_details", {}).get("name", ""),
            #             "total_score": result.get("total_score", 0),
            #             "max_score": result.get("max_possible_score", 10),
            #             "job_id": job_id,
            #             "position": job_config["position"]
            #         }
            #     })
            #     break


            # Check if workflow completed
            snapshot = graph_app.get_state(config)
            if not snapshot.next:
                result = snapshot.values
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


if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)