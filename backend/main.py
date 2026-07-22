"""FastAPI WebSocket server for screening chatbot"""

import datetime
import sys
import time
import re as _re
import traceback as _tb
from typing import Optional
from fastapi import FastAPI, Request, Response, WebSocket, WebSocketDisconnect, HTTPException, Body, APIRouter, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.security.api_key import APIKeyHeader
from langchain.schema import HumanMessage, AIMessage
import json
import uuid

from requests import session
from xano_jobs import fetch_job_specific_qualifiers
from graph import build_graph, ChatbotState
from graph import build_graph, ChatbotState
from passport_creation.passport_graph import build_passport_graph, PassportState
from passport_creation.passport_configs import PASSPORT_CONFIG
from job_configs import JOB_CONFIGS
# from xano_jobs import read_job_config_from_db

from contextlib import asynccontextmanager
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg import AsyncConnection
from psycopg.rows import dict_row
import os
import asyncio
from location_services import get_address_autocomplete, get_place_details, reverse_geocode

from id_verification import (
    setup_mapping_table,
    save_session_mapping,
    get_cleo_session_id,
    verify_webhook_signature,
)

from conversation_logger import (
    setup_log_tables,
    init_run,
    log_event,
    log_router,
    log_error,
    update_run_status,
)
from conversation_logger import log_id_verification_event

# Prevent duplicate webhook processing for same Simplici session
processed_webhook_sessions: set = set()
webhook_dedup_lock = asyncio.Lock()

brand_name = ""
current_session_id = ""

# Initialize graph at startup
graph_app = None
passport_graph_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_app
    global passport_graph_app
    
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

    await setup_mapping_table()    # creates id_verify_sessions table

    await setup_log_tables()       # creates conversation_runs + conversation_events tables
    print("[LOGGER] Log tables initialized")
    
    # Build graph with checkpointer
    graph_app = build_graph(checkpointer)
    passport_graph_app = build_passport_graph(checkpointer)
    print("Job graph and Passport graph initialized with AsyncPostgresSaver")

    # START CLEANUP TASK
    cleanup_task = asyncio.create_task(cleanup_inactive_sessions())
    print("Session cleanup task started")
    
    yield
    
    # CANCEL CLEANUP TASK ON SHUTDOWN
    cleanup_task.cancel()
    # Cleanup
    await conn.close()
    print("Connection closed")

# Update FastAPI initialization
app = FastAPI(title="Screening Chatbot API", lifespan=lifespan)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
   allow_origins=["https://scanandhire.com", "http://localhost:8000", "http://localhost:3000", "http://127.0.0.1:5500" ,"https://bigchicken.vercel.app", "https://burgerking-olive.vercel.app", "https://mcdonald-eta.vercel.app", "https://popeyes-ten.vercel.app", "https://starbucks-virid-three.vercel.app"],
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
]

Brand_names = {
    "bigchicken.vercel.app": "Big Chicken",
    "burgerking-olive.vercel.app": "Burger King",
    "mcdonald.vercel.app": "McDonald's",
    "popeyes.vercel.app": "Popeyes",
    "starbucks.vercel.app": "Starbucks",
    "127.0.0.1": "Big Chicken",
    "scanandhire.com": "Big Chicken",
    "localhost": "Big Chicken"
}

# API key for authenticated requests
API_KEY = "test_key_secure_123"

# Store active sessions
sessions = {}

@app.get("/favicon.ico")
async def favicon():
    """Return empty response for favicon"""
    return Response(status_code=204)

@app.get("/")
async def root():
    """Serve test page"""
    with open("./client-websites/big_chicken_frontend/index.html", "r") as f:
        return HTMLResponse(content=f.read())

@app.get("/job-details")
async def job_details():
    """Serve job details page"""
    return FileResponse("job_details.html", media_type="text/html")

@app.get("/create-passport")
async def create_passport():
    """Serve passport creation page"""
    return FileResponse("passport_creation/create_profile.html", media_type="text/html")

@app.get("/job-details-test")
async def job_details_test():
    """Serve job details page"""
    return FileResponse("job_details_test.html", media_type="text/html")    
    

@app.get("/cleoAssistant.js")
async def serve_embed_script():
    """Serve the chatbot embed script"""
    return FileResponse("cleoAssistant.js", media_type="application/javascript",  headers={"Cache-Control": "no-store"})

@app.get("/config.js")
async def serve_config_script():
    """Serve the config script"""
    return FileResponse("config.js", media_type="application/javascript", headers={"Cache-Control": "no-store"})


@app.get("/cleo-typography.css")
async def serve_css():
    """Serve the CSS file"""
    return FileResponse("cleo-typography.css", media_type="text/css", headers={"Cache-Control": "no-store"})


@app.get("/places/reverse-geocode")
async def reverse_geocode_coords(lat: float = Query(...), lng: float = Query(...)):
    """
    Convert GPS coordinates to a human-readable address.
    Returns: { formatted_address, components: { city, state, zip, country } }
    """
    result = reverse_geocode(lat, lng)
    if not result:
        raise HTTPException(status_code=404, detail="Location not found")
    return result


@app.get("/places/autocomplete")
async def places_autocomplete(input: str = Query(...), session_token: str = Query("")):
    """
    Proxy for Google Places Autocomplete.
    Keeps the API key on the server (never exposed to frontend).
    """
    if len(input.strip()) < 3:
        return {"predictions": []}

    suggestions = get_address_autocomplete(input.strip(), session_token)
    return {"predictions": suggestions}


@app.get("/places/details")
async def place_details(place_id: str = Query(...)):
    """
    Get structured address details from a Google place_id.
    Returns: { street, city, state, zip, full, lat, lng }
    """
    details = get_place_details(place_id)
    if not details:
        raise HTTPException(status_code=404, detail="Place not found")
    return details


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

    print(f"Validating domain endpoint hitted for domain: {domain}")
    
    # Validate domain against ALLOWED_DOMAINS list
    if "*" not in ALLOWED_DOMAINS:
        # Strict domain checking
        if domain not in ALLOWED_DOMAINS:
            raise HTTPException(
                status_code=403,
                detail=f"Domain '{domain}' is not authorized"
            )
    
    global brand_name
    if domain == "scanandhire.com":
        brand_name = "Big Chicken"
    else:
        brand_name = Brand_names.get(domain, "")

    # Return API key if validation passes
    return {
        "apiKey": API_KEY
    }


@app.post("/start-passport-session")
async def start_passport_session(
    api_key:  str  = Body(...),
    is_live:  bool = Body(default=False),
):
    

    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    session_id = str(uuid.uuid4())
    thread_id  = f"thread_passport_{session_id}"

    sessions[session_id] = {
        "thread_id":             thread_id,
        "job_type":              "passport",
        "location":              "",
        "job_id":                "",
        "company_id":            "",
        "is_live":               is_live,
        "active":                True,
        "created_at":            time.time(),
        "last_activity":         time.time(),
        "job_shift":             "",
        "brand_name":            "Cleo Work Passport™",
        "single_company":        False,
        "verification_required": False,
        "job_template_id":       "",
    }

    return {
        "session_id": session_id,
        "mode":       "passport",
    }

@app.post("/start-session")
async def start_session(request: Request):
    """Create new screening session for a specific job type"""

    data       = await request.json()
    api_key    = data.get("api_key")
    job_type   = data.get("job_type")
    location   = data.get("location")
    job_id     = data.get("job_id")
    company_id = data.get("company_id")
    is_live    = data.get("is_live", False)
    job_shift  = data.get("job_shift", "various shifts")
    brand_name = data.get("brand_name", "our company")
    verification_required = data.get("verification_required", False)
    single_company = data.get("single_company", False)
    template_id = data.get("job_template_id", "default_template")


    print(f"Starting session for job_type: {job_type} at location: {location}")

    # job_configs = await read_job_config_from_db()

    # Validate job_id exists
    if job_type not in JOB_CONFIGS:
        raise HTTPException(status_code=404, detail="Job type not found")
    
    # Validate API key
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    # Create session
    session_id = str(uuid.uuid4())
    global current_session_id
    current_session_id = session_id

    thread_id = f"thread_{job_type}_{session_id}"
    
    sessions[session_id] = {
        "thread_id": thread_id,
        "job_type": job_type,
        "location": location,
        "job_id": job_id,
        "company_id": company_id,
        "is_live": is_live,
        "job_shift": job_shift,
        "active": True,
        "created_at": time.time(),
        "last_activity": time.time(),  # Track last activity
        "brand_name": brand_name,
        "job_shift":  job_shift,
        "verification_required": verification_required,
        "single_company": single_company,
        "job_template_id": template_id
    }

    # Log new run
    asyncio.create_task(init_run(
        session_id=session_id,
        thread_id=thread_id,
        job_type=job_type,
        brand_name=brand_name,
        location=location,
    ))
    
    return {
        "session_id": session_id,
        "job_type": job_type,
        "position": job_type.replace('_', ' ').title(),
    }


def set_job_address(job_config: dict, location: str):

    # Replace placeholder in knockout questions
    job = job_config.copy()
    job["knockout_questions"] = [
        q.format(address=location) for q in job["knockout_questions"]
    ]

    # print(f"Updated Job ->: {job}")

    return job


async def websocket_heartbeat(websocket: WebSocket):
    """
    Send ping every 30 seconds to keep connection alive.
    AWS ALB/Nginx timeout is 60s, so ping at 30s keeps it well below threshold.
    """
    try:
        while True:
            await asyncio.sleep(30)  # Ping every 30 seconds
            try:
                await websocket.send_json({"type": "ping"})
                # print(f"[HEARTBEAT] Sent ping")
            except Exception as e:
                print(f"[HEARTBEAT] Failed to send ping: {e}")
                break  # Connection lost, exit heartbeat
    except asyncio.CancelledError:
        print("[HEARTBEAT] Heartbeat task cancelled")


async def cleanup_inactive_sessions():
    """
    Background task to remove sessions inactive for more than 10 minutes.
    Runs every 60 seconds.
    """
    while True:
        try:
            await asyncio.sleep(60)  # Check every minute
            
            current_time = time.time()
            inactive_sessions = []
            
            # Find sessions inactive for > 10 minutes (600 seconds)
            for session_id, session in sessions.items():
                last_activity = session.get("last_activity", 0)
                inactive_duration = current_time - last_activity
                
                if inactive_duration > 600:  # 10 minutes
                    inactive_sessions.append(session_id)
                    print(f"[CLEANUP] Session {session_id} inactive for {inactive_duration:.0f}s")
            
            # Remove inactive sessions
            for session_id in inactive_sessions:
                print(f"[CLEANUP] Removing session: {session_id}")
                del sessions[session_id]
            
            if inactive_sessions:
                print(f"[CLEANUP] Removed {len(inactive_sessions)} inactive session(s)")
                print(f"[CLEANUP] Active sessions remaining: {len(sessions)}")
        
        except Exception as e:
            print(f"[CLEANUP] Error in cleanup task: {e}")




@app.post("/webhook/id-verification")
async def id_verification_webhook(request: Request):
    """
    Receives Simplici webhook when ID verification completes.
    Updates graph state and pushes real-time result to the active WebSocket.
    """
    raw_body = await request.body()

    # ── Optional: verify Simplici signature ──────────────────────────────────
    # signature = request.headers.get("X-Simplici-Signature", "")
    # if not verify_webhook_signature(raw_body, signature):
    #     raise HTTPException(status_code=401, detail="Invalid webhook signature")

    payload = await request.json()
    print(f"[WEBHOOK] ID verification payload received: {payload}")

    simplici_session_id = payload.get("sessionId")
    step_id = payload.get("stepId", "")

    processed_webhook_sessions.add(simplici_session_id)

    if step_id == "sessionInitiate":
        simplici_session_id = payload.get("sessionId")
        cleo_session_id = current_session_id  
        await save_session_mapping(simplici_session_id, cleo_session_id)
        
        print(f"[WEBHOOK] Session initiated. Simplici session {simplici_session_id} mapped to Cleo session {cleo_session_id}")
        return {"status": "handled"}

    # Early exit for intermediate steps
    if step_id != "kyc":
        print(f"[WEBHOOK] Ignoring step: {step_id}")
        return {"status": "ignored"}

    # ── Atomic deduplication guard ────────────────────────────────────────────
    kyc_key = f"kyc_{simplici_session_id}"
    async with webhook_dedup_lock:
        if kyc_key in processed_webhook_sessions:
            print(f"[WEBHOOK] Duplicate kyc call ignored for session {simplici_session_id}")
            return {"status": "already_processed"}
        processed_webhook_sessions.add(kyc_key)
    
    event_payload = payload.get("payload", {})

    if not simplici_session_id:
        raise HTTPException(status_code=400, detail="Missing sessionId")

    # ── Look up which Cleo session this belongs to ────────────────────────────
    cleo_session_id = await get_cleo_session_id(simplici_session_id)

    if not cleo_session_id:
        print(f"[WEBHOOK] No Cleo session found for Simplici session {simplici_session_id}")
        # Return 200 so Simplici doesn't keep retrying
        return {"status": "session_not_found"}

    # Determine pass/fail from Simplici schema
    kyc_data      = event_payload.get("kyc", {})
    report        = kyc_data.get("basicInfo", {}).get("report", {})
    top_status    = event_payload.get("status", "")
    report_status = report.get("status", "")
    rejections    = report.get("reject", ["unknown"])  # non-empty = failed
    liveliness    = report.get("liveliness", False)

    verified = (
        top_status    == "completed" and
        report_status == "completed" and
        liveliness    == True and
        len(rejections) == 0
    )

    print(f"[WEBHOOK] KYC result — status: {top_status}, report: {report_status}, liveliness: {liveliness}, rejections: {rejections}, verified: {verified}")

    print(f"[WEBHOOK] Session {cleo_session_id} — verified: {verified}")

    # ── Update LangGraph state directly ──────────────────────────────────────
    session   = sessions.get(cleo_session_id)
    if not session:
        return {"status": "session_inactive"}

    thread_id = session["thread_id"]
    config    = {"configurable": {"thread_id": thread_id}}

    current_state    = await graph_app.aget_state(config)
    current_messages = current_state.values.get("messages", [])

    await graph_app.aupdate_state(
        config,
        {
            "id_verified":      verified,
            "id_verify_failed": not verified,
        }
    )

    # ── Log id verification result ────────────────────────────────────────────
    await log_event(cleo_session_id, thread_id, "process_id_result", "otp_verify",
                    {"channel": "id_verification", "success": verified})


# ── Auto-resume graph in background — return 200 immediately ─────────────
    current_messages = current_state.values.get("messages", [])
    await graph_app.aupdate_state(
        config,
        {"messages": current_messages + [HumanMessage(content="id_verify_webhook")]}
    )

    ws = session.get("websocket")

    async def stream_and_notify():
        try:
            # Log pass/fail result
            await log_id_verification_event(
                session_id=cleo_session_id, thread_id=thread_id,
                status="id_verify_passed" if verified else "id_verify_failed",
                raw_data={
                    "simplici_session_id": simplici_session_id,
                    "top_status":    event_payload.get("status", ""),
                    "report_status": event_payload.get("kyc", {}).get("basicInfo", {}).get("report", {}).get("status", ""),
                    "liveliness":    event_payload.get("kyc", {}).get("basicInfo", {}).get("report", {}).get("liveliness", False),
                    "rejections":    event_payload.get("kyc", {}).get("basicInfo", {}).get("report", {}).get("reject", []),
                    "verified":      verified,
                }
            )
            # ── Close modal immediately ───────────────────────────────────────
            if ws:
                await ws.send_json({"type": "id_verify_result", "verified": verified})
                print(f"[WEBHOOK] Modal close signal sent for {cleo_session_id}")

            # Only these nodes add new messages — all others are skipped
            NODES_WITH_NEW_MESSAGES = {"process_id_result", "end", "delay_messages"}

            async for event in graph_app.astream(None, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    await log_event(cleo_session_id, thread_id, node_name, "node_enter",
                                    {"state_keys": list(node_data.keys()) if node_data else []})

                     # ── Show typing indicator during heavy compute nodes ──────────────
                    if node_name in ("score", "summary") and ws:
                        try:
                            await ws.send_json({"type": "typing"})
                        except Exception:
                            pass
                        continue   # still skip sending messages for these nodes
                    
                    
                    # Skip nodes that don't add new messages
                    if node_name not in NODES_WITH_NEW_MESSAGES:
                        continue

                    if node_data and "messages" in node_data and ws:
                        if node_name in ("process_id_result"):
                            msgs_to_send = node_data["messages"][-2:]
                        elif node_name == "delay_messages":
                            msgs_to_send = node_data["messages"][-3:]   
                        else:
                            msgs_to_send = node_data["messages"][-1:]

                        for msg in msgs_to_send:
                            if isinstance(msg, AIMessage):
                                await ws.send_json({"type": "typing"})
                                await asyncio.sleep(0.7)
                                await asyncio.sleep(1.0)
                                await ws.send_json({
                                    "type": "ai_message",
                                    "content": msg.content,
                                    "messageType": "body"
                                })
                                await log_event(cleo_session_id, thread_id, node_name, "ai_message",
                                                {"content": msg.content, "messageType": "body"})

        except Exception as e:
            # Log system error
            await log_id_verification_event(
                session_id=cleo_session_id, thread_id=thread_id,
                status="id_verify_system_error",
                raw_data={"simplici_session_id": simplici_session_id},
                error=str(e)
            )
            print(f"[WEBHOOK] Error in background stream: {e}")


    asyncio.create_task(stream_and_notify())

    return {"status": "ok", "verified": verified}  # ← returns immediately to Simplici




# Nodes that do NOT add new messages — skip to avoid sending stale messages[-1]
NODES_WITHOUT_MESSAGES = {
    "score", "summary",
    "process_gps", "store_address",
    "phone_router", "email_router", "question_router",
    "phone_otp_router", "email_otp_router", "background_check_router",
    "military_router", "single_knockout_router", "post_acknowledgement_router",
    "id_verification_router",
    "send_email_otp",
    "send_phone_otp",   
}
 

@app.websocket("/passport/ws/{session_id}")
async def passport_websocket_endpoint(websocket: WebSocket, session_id: str):
    
    global passport_graph_app
    await websocket.accept()

    if session_id not in sessions:
        await websocket.send_json({"type": "error", "message": "Invalid session ID"})
        await websocket.close()
        return

    heartbeat_task = asyncio.create_task(websocket_heartbeat(websocket))

    session    = sessions[session_id]
    sessions[session_id]["websocket"] = websocket
    thread_id  = session["thread_id"]
    is_live    = session["is_live"]

    config = {"configurable": {"thread_id": thread_id}}

    try:
        # ── Reconnection check ────────────────────────────────────────────────
        existing_state = await passport_graph_app.aget_state(config)

        if existing_state.values and existing_state.values.get("messages"):
            print(f"[PASSPORT RECONNECT] Existing state found for {session_id}")
        else:
            # ── New session — build initial PassportState ─────────────────────
            print(f"[PASSPORT NEW SESSION] Starting for {session_id}")

            initial_state = PassportState(
                messages                        = [],
                session_id                      = session_id,
                is_live                         = is_live,
                passport_id                     = 0,
                passport_link                   = "",
                passport_profile                = {},
                privacy_consented               = False,
                personal_details                = {},
                knockout_questions              = PASSPORT_CONFIG["knockout_questions"],
                knockout_answers                = {},
                current_knockout_question_index = 0,
                knockout_passed                 = False,
                current_knockout_failed         = False,
                shift_preferences               = [],
                address                         = {},
                commute_method                  = "",
                show_address_ui                 = False,
                questions                       = PASSPORT_CONFIG["questions"],
                answers                         = {},
                current_question_index          = 0,
                scoring_model                   = PASSPORT_CONFIG["scoring_model"],
                email_validation_failed         = False,
                invalid_email_attempt           = "",
                email_attempt_count             = 0,
                email_hard_stop                 = False,
                email_otp_code                  = "",
                email_otp_sent                  = False,
                email_otp_sent_failed           = False,
                email_otp_timestamp             = 0,
                email_verified                  = False,
                email_otp_attempts              = 0,
                phone_validation_failed         = False,
                invalid_phone_attempt           = "",
                phone_attempt_count             = 0,
                phone_otp_code                  = "",
                phone_otp_sent                  = False,
                phone_otp_sent_failed           = False,
                phone_otp_timestamp             = 0,
                phone_verified                  = False,
                phone_otp_attempts              = 0,
                phone_verify_session_uuid       = "",
                work_experience                 = [],
                show_work_experience_ui         = False,
                education_level                 = "",
                show_education_ui               = False,
                military_served                 = False,
                military_details                = {},
                military_follow_up_done         = False,
                id_verify_link                  = "",
                id_verify_session_id            = "",
                id_verified                     = False,
                id_verify_failed                = False,
                show_id_verify_ui               = False,
                re_ask_attempts                 = {},
                answer_reask_reason             = "",
                kq_reask_reason                 = "",
                show_privacy_consent_ui         = False
            )

            # Stream initial graph run (greeting bubbles)
            async for event in passport_graph_app.astream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    if node_name in {"ask_name"}:
                        continue
                    if node_data and "messages" in node_data:
                        messages = node_data["messages"]

                        # Greeting: send all 3 bubbles with stagger
                        if node_name == "passport_greeting":
                            bubbles = messages[-3:]
                            for i, msg in enumerate(bubbles):
                                if isinstance(msg, AIMessage):
                                    await websocket.send_json({"type": "typing"})
                                    await asyncio.sleep(0.8)
                                    await asyncio.sleep(1.2)
                                    is_last = (i == len(bubbles) - 1)
                                    await websocket.send_json({
                                        "type":                   "ai_message",
                                        "content":                msg.content,
                                        "messageType":            "intro",
                                        "show_privacy_consent_ui": is_last and node_data.get("show_privacy_consent_ui", False),
                                    })
                        else:
                            msg = messages[-1]
                            if isinstance(msg, AIMessage):
                                await websocket.send_json({"type": "typing"})
                                await asyncio.sleep(0.7)
                                await websocket.send_json({
                                    "type":        "ai_message",
                                    "content":     msg.content,
                                    "messageType": "intro",
                                })

        # ── Main message loop ─────────────────────────────────────────────────
        while True:

            snapshot = await passport_graph_app.aget_state(config)
            if not snapshot.next:
                await websocket.send_json({"type": "workflow_complete"})
                break

            data         = await websocket.receive_text()
            message_data = json.loads(data)

            if session_id in sessions:
                sessions[session_id]["last_activity"] = time.time()

            print(f"[PASSPORT WS] Received: {message_data}")

            # ── Heartbeat ─────────────────────────────────────────────────────
            if message_data.get("type") == "pong":
                continue
            if message_data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # ── State sync (reconnection) ─────────────────────────────────────
            if message_data.get("type") == "sync_state":
                snapshot    = await passport_graph_app.aget_state(config)
                next_nodes  = snapshot.next if snapshot else []
                await websocket.send_json({
                    "type":       "state_synced",
                    "message":    "Connection restored. You can continue where you left off.",
                    "next_nodes": next_nodes,
                })
                continue

            # ── Address data from autocomplete UI ─────────────────────────────
            if message_data.get("type") == "address_data":
                address_payload = message_data.get("data", {})
                print(f"[PASSPORT WS] Address received: {address_payload}")

                current_state    = await passport_graph_app.aget_state(config)
                current_messages = current_state.values.get("messages", [])

                import json as _json
                address_message = _json.dumps(address_payload)

                await passport_graph_app.aupdate_state(
                    config,
                    {
                        "address":  address_payload,
                        "messages": current_messages + [HumanMessage(content=address_message)],
                    }
                )

                async for event in passport_graph_app.astream(None, config=config, stream_mode="updates"):
                    for node_name, node_data in event.items():
                        print(f"[PASSPORT NODE] {node_name}")
                        if node_data and "messages" in node_data:
                            messages = node_data["messages"]
                            msg      = messages[-1]
                            if isinstance(msg, AIMessage):
                                await websocket.send_json({"type": "typing"})
                                await asyncio.sleep(0.7)
                                await websocket.send_json({
                                    "type":        "ai_message",
                                    "content":     msg.content,
                                    "messageType": "body",
                                })
                continue

            # ── Shift preference (checkbox selection) ─────────────────────────
            if message_data.get("type") == "shift_selection":
                selected_shifts = message_data.get("data", [])
                print(f"[PASSPORT WS] Shifts selected: {selected_shifts}")

                current_state    = await passport_graph_app.aget_state(config)
                current_messages = current_state.values.get("messages", [])

                import json as _json
                shift_message = _json.dumps(selected_shifts)

                await passport_graph_app.aupdate_state(
                    config,
                    {"messages": current_messages + [HumanMessage(content=shift_message)]}
                )

                async for event in passport_graph_app.astream(None, config=config, stream_mode="updates"):
                    for node_name, node_data in event.items():
                        print(f"[PASSPORT NODE] {node_name}")
                        if node_data and "messages" in node_data:
                            messages = node_data["messages"]
                            msg      = messages[-1]
                            if isinstance(msg, AIMessage):
                                show_address_ui = (
                                    node_name == "ask_address" and
                                    node_data.get("show_address_ui", False)
                                )
                                await websocket.send_json({"type": "typing"})
                                await asyncio.sleep(0.7)
                                await websocket.send_json({
                                    "type":            "ai_message",
                                    "content":         msg.content,
                                    "messageType":     "body",
                                    "show_address_ui": show_address_ui,
                                })
                continue

            # ── Work experience UI submission ─────────────────────────────────
            if message_data.get("type") == "work_experience_data":
                work_exp_payload = message_data.get("data", [])
                print(f"[PASSPORT WS] Work experience received: {work_exp_payload}")

                current_state    = await passport_graph_app.aget_state(config)
                current_messages = current_state.values.get("messages", [])

                await passport_graph_app.aupdate_state(
                    config,
                    {
                        "work_experience": work_exp_payload,
                        "messages":        current_messages + [HumanMessage(content="Work experience submitted.")],
                    }
                )

                async for event in passport_graph_app.astream(None, config=config, stream_mode="updates"):
                    for node_name, node_data in event.items():
                        print(f"[PASSPORT NODE] {node_name}")
                        if node_data and "messages" in node_data:
                            messages = node_data["messages"]
                            msg      = messages[-1]
                            if isinstance(msg, AIMessage):
                                show_edu_ui = (
                                    node_name == "ask_education" and
                                    node_data.get("show_education_ui", False)
                                )
                                await websocket.send_json({"type": "typing"})
                                await asyncio.sleep(0.7)
                                await websocket.send_json({
                                    "type":             "ai_message",
                                    "content":          msg.content,
                                    "messageType":      "body",
                                    "show_education_ui": show_edu_ui,
                                })
                continue

            # ── ID verification result (pushed by webhook) ────────────────────
            if message_data.get("type") == "id_verify_result":
                verified = message_data.get("verified", False)

                current_state    = await passport_graph_app.aget_state(config)
                current_messages = current_state.values.get("messages", [])

                await passport_graph_app.aupdate_state(
                    config,
                    {
                        "id_verified":      verified,
                        "id_verify_failed": not verified,
                        "messages":         current_messages + [HumanMessage(content="id_verification_complete")],
                    }
                )

                async for event in passport_graph_app.astream(None, config=config, stream_mode="updates"):
                    for node_name, node_data in event.items():
                        print(f"[PASSPORT NODE] {node_name}")
                        if node_data and "messages" in node_data:
                            messages = node_data["messages"]
                            for msg in messages[-4:]:   # W1-W4 wrap-up bubbles
                                if isinstance(msg, AIMessage):
                                    await websocket.send_json({"type": "typing"})
                                    await asyncio.sleep(0.8)
                                    await asyncio.sleep(1.0)
                                    await websocket.send_json({
                                        "type":        "ai_message",
                                        "content":     msg.content,
                                        "messageType": "body",
                                    })
                continue

            # ── Normal text message ───────────────────────────────────────────
            if message_data.get("type") != "user_message":
                print(f"[PASSPORT WS] Skipping non-user message: {message_data.get('type')}")
                continue

            user_input = str(message_data.get("content") or "").strip()
            if not user_input:
                continue

            current_state    = await passport_graph_app.aget_state(config)
            current_messages = current_state.values.get("messages", [])

            await passport_graph_app.aupdate_state(
                config,
                {"messages": current_messages + [HumanMessage(content=user_input)]}
            )

            print(f"[PASSPORT WS] Resuming workflow")

            async for event in passport_graph_app.astream(None, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    print(f"[PASSPORT NODE] {node_name}")

                    # Nodes that don't add new messages — skip
                    if node_name in {"privacy_router", "name_router"}:
                        continue

                    if node_data and "messages" in node_data:
                        messages = node_data["messages"]

                        # ID verification — send 2 messages with stagger
                        if node_name == "ask_id_verification":
                            for msg in messages[-2:]:
                                if isinstance(msg, AIMessage):
                                    await websocket.send_json({"type": "typing"})
                                    await asyncio.sleep(0.7)
                                    await asyncio.sleep(1.2)
                                    is_last = (msg == messages[-1])
                                    await websocket.send_json({
                                        "type":             "ai_message",
                                        "content":          msg.content,
                                        "messageType":      "body",
                                        "show_id_verify_ui": is_last,
                                        "id_verify_link":   node_data.get("id_verify_link", "") if is_last else "",
                                    })
                            continue

                        # passport_summary sends 4 wrap-up bubbles — send all
                        if node_name == "passport_summary":
                            for msg in messages[-4:]:
                                if isinstance(msg, AIMessage):
                                    await websocket.send_json({"type": "typing"})
                                    await asyncio.sleep(0.8)
                                    await asyncio.sleep(1.0)
                                    await websocket.send_json({
                                        "type":        "ai_message",
                                        "content":     msg.content,
                                        "messageType": "body",
                                    })
                            continue

                        msg = messages[-1]
                        if isinstance(msg, AIMessage):

                            messageType = "questions" if node_name in [
                                "ask_name",
                                "ask_knockout_question",
                                "ask_question",
                                "ask_email",
                                "ask_email_otp",
                                "ask_phone",
                                "ask_phone_otp",
                                "ask_work_experience",
                                "ask_education",
                                "ask_military",
                            ] else "body"

                            show_address_ui = (
                                node_name == "ask_address" and
                                node_data.get("show_address_ui", False)
                            )
                            show_shift_ui = (
                                node_name == "ask_shift_preference"
                            )
                            show_edu_ui = (
                                node_name == "ask_education" and
                                node_data.get("show_education_ui", False)
                            )
                            show_work_ui = (
                                node_name == "store_work_experience_response" and
                                node_data.get("show_work_experience_ui", False)
                            )

                            await websocket.send_json({"type": "typing"})
                            await asyncio.sleep(0.7)
                            await websocket.send_json({
                                "type":                    "ai_message",
                                "content":                 msg.content,
                                "messageType":             messageType,
                                "show_address_ui":         show_address_ui,
                                "show_shift_ui":           show_shift_ui,
                                "show_education_ui":       show_edu_ui,
                                "show_work_experience_ui": show_work_ui,
                            })

    except WebSocketDisconnect:
        print(f"[PASSPORT WS] Client disconnected: {session_id}")
        sessions[session_id]["active"] = False
        heartbeat_task.cancel()

    except Exception as e:
        import traceback
        print(f"[PASSPORT WS] Error: {e}")
        print(traceback.format_exc())
        heartbeat_task.cancel()
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()

    finally:
        if not heartbeat_task.done():
            heartbeat_task.cancel()


@app.websocket("/ws/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket connection for chat"""
    await websocket.accept()
 
    if session_id not in sessions:
        await websocket.send_json({"type": "error", "message": "Invalid session ID"})
        await websocket.close()
        return
 
    # Start heartbeat task
    heartbeat_task = asyncio.create_task(websocket_heartbeat(websocket))
 
    session    = sessions[session_id]
    sessions[session_id]["websocket"] = websocket
    thread_id  = session["thread_id"]
    job_type   = session["job_type"]
    location   = session["location"]
    job_id     = session["job_id"]
    company_id = session["company_id"]
    is_live    = session["is_live"]
    job_shift  = session["job_shift"]
    template_id = session["job_template_id"]
    single_company = session["single_company"]
 
    job_config = JOB_CONFIGS[job_type]
    job        = set_job_address(job_config, location)

    session["thread_id"]
    
    brand_name = session["brand_name"]
    job_shift  = session["job_shift"]
    verification_required = session["verification_required"]
  
    config = {"configurable": {"thread_id": thread_id}}
 
    # ── Helper: send a single AIMessage with typing indicator ─────────────────
    async def send_message(msg, node_name, message_type="body", extra=None):
        if not isinstance(msg, AIMessage):
            return
        await websocket.send_json({"type": "typing"})
        await asyncio.sleep(0.5)
        payload = {
            "type":        "ai_message",
            "content":     msg.content,
            "messageType": message_type,
        }
        if extra:
            payload.update(extra)
        await websocket.send_json(payload)
        await log_event(session_id, thread_id, node_name, "ai_message",
                        {"content": msg.content, "messageType": message_type})
 
    # ── Helper: process a single node's output and send messages ──────────────
    async def process_node(node_name, node_data, context="normal"):
        if not node_data or "messages" not in node_data:
            return
 
        # Skip nodes that don't add new messages
        if node_name in NODES_WITHOUT_MESSAGES:
            return
 
        messages = node_data["messages"]
 
        # ── delay_messages: send last 3 with extra delay ──────────────────────
        if node_name == "delay_messages":
            delay_type = node_data.get("delay_node_type", "greeting")
            count = 3 if delay_type == "end" else 2
            for msg in messages[-count:]:
                if isinstance(msg, AIMessage):
                    await websocket.send_json({"type": "typing"})
                    await asyncio.sleep(0.5)
                    await asyncio.sleep(1)
                    await websocket.send_json({
                        "type":        "ai_message",
                        "content":     msg.content,
                        "messageType": "body"
                    })
                    await log_event(session_id, thread_id, node_name, "ai_message",
                                    {"content": msg.content, "messageType": "body"})
            return
 
        # ── ask_id_verification: send last 3 messages, UI on last ─────────────
        if node_name == "ask_id_verification":
            delay_type = node_data.get("delay_node_type", "greeting")
            count = 3 if delay_type == "end" else 2
            for msg in messages[-count:]:
                if isinstance(msg, AIMessage):
                    is_last       = (msg == messages[-1])
                    id_verify_ui  = is_last
                    id_verify_lnk = node_data.get("id_verify_link", "") if is_last else ""
                    await websocket.send_json({"type": "typing"})
                    await asyncio.sleep(0.5)
                    await websocket.send_json({
                        "type":             "ai_message",
                        "content":          msg.content,
                        "messageType":      "body",
                        "show_id_verify_ui": id_verify_ui,
                        "id_verify_link":   id_verify_lnk,
                    })
                    await log_event(session_id, thread_id, node_name, "ai_message",
                                    {"content": msg.content, "messageType": "body"})
            return
 
        # ── All other nodes: send last message only ───────────────────────────
        msg = messages[-1]
        if not isinstance(msg, AIMessage):
            return
 
        # Determine messageType
        question_nodes = {
            "ask_knockout_question", "ask_name", "ask_email", "ask_phone",
            "ask_question", "ask_work_experience", "ask_education",
            "ask_certifications", "ask_military", "ask_background_check",
            "ask_referral", "ask_id_verification"
        }
        message_type = "questions" if node_name in question_nodes else "body"
 
        # UI flags
        extra = {
            "show_work_experience_ui": node_name == "store_work_experience_response" and node_data.get("show_work_experience_ui", False),
            "show_education_ui":       node_name == "ask_education"          and node_data.get("show_education_ui", False),
            "show_address_ui":         node_name == "ask_address"            and node_data.get("show_address_ui", False),
            "show_gps_ui":             node_name == "ask_gps_verification"   and node_data.get("show_gps_ui", False),
            "show_id_verify_ui":       False,
            "id_verify_link":          "",
        }
 
        await send_message(msg, node_name, message_type, extra)
 
    try:
        # ── CHECK IF STATE ALREADY EXISTS (reconnection) ──────────────────────
        existing_state = await graph_app.aget_state(config)
 
        if existing_state.values and existing_state.values.get("messages"):
            print(f"[RECONNECT] Existing state found for {session_id}, skipping initial workflow")
            print(f"[RECONNECT] Message count: {len(existing_state.values.get('messages', []))}")
        else:
            # ── NEW SESSION — start fresh workflow ────────────────────────────
            print(f"[NEW SESSION] No existing state, starting new workflow for {session_id}")

            qualifiers = await fetch_job_specific_qualifiers(template_id)
 
            initial_state = ChatbotState(
                messages=[],
                questions=qualifiers["questions"],
                scoring_model={**job["scoring_model"], **qualifiers["scoring_model"]},
                required_questions=qualifiers["required_questions"],
                flagged_questions=qualifiers["flagged_questions"],
                question_acknowledgements=qualifiers["question_acknowledgements"],
    
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
                current_knockout_failed=False,
                email_otp_code="",
                email_otp_sent=False,
                email_otp_sent_failed=False,
                email_otp_timestamp=0,
                email_verified=False,
                email_otp_attempts=0,
                phone_otp_code="",
                phone_otp_sent=False,
                phone_otp_sent_failed=False,
                phone_otp_timestamp=0,
                phone_verified=False,
                phone_otp_attempts=0,
                phone_verify_session_uuid="",
                id_verify_link="",
                id_verify_session_id="",
                id_verified=False,
                id_verify_failed=False,
                show_id_verify_ui=False,
                session_id=session_id,
                job_id=job_id,
                company_id=company_id,
                is_live=is_live,
                applicant_age="",
                work_experience=[],
                show_work_experience_ui=False,
                education_level="",
                show_education_ui=False,
                address={},
                show_address_ui=False,
                gps_lat=0.0,
                gps_lng=0.0,
                gps_verified=False,
                gps_flagged=False,
                gps_flag_reason="",
                gps_distance_miles=0.0,
                show_gps_ui=False,
                job_type=job_type,
                certifications=[],
                military_served=False,
                military_details={},
                military_follow_up_done=False,
                background_check_consented=False,
                referral_source="",
                education_year="",
                verification_required=verification_required,

                brand_name=brand_name,
                job_shift=job_shift,

                experience_qualified=True,
                re_ask_attempts={},
                required_question_failed=False,              
                manager_flags=[],
                end_conversation=False,
                phone_hard_stop=False,
                kq_ambiguous_default=False,
                generic_fail=False,
                email_hard_stop=False,
                single_company=single_company,
                incomplete_application=False,
                kq_reask_reason="",
                answer_reask_reason="",
                job_location=location,
                candidate_id= 0,
                profile_summary={}
            )
 
            async for event in graph_app.astream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    await log_event(session_id, thread_id, node_name, "node_enter",
                                    {"state_keys": list(node_data.keys()) if node_data else []})
 
                    if node_data and "messages" in node_data:
                        messages = node_data["messages"]
 
                        if node_name == "delay_messages":
                            delay_type = node_data.get("delay_node_type", "greeting")
                            count = 3 if delay_type == "end" else 2
                            for msg in messages[-count:]:
                                if isinstance(msg, AIMessage):
                                    await websocket.send_json({"type": "typing"})
                                    await asyncio.sleep(0.5)
                                    await asyncio.sleep(1)
                                    await websocket.send_json({
                                        "type":        "ai_message",
                                        "content":     msg.content,
                                        "messageType": "body"
                                    })
                                    await log_event(session_id, thread_id, node_name, "ai_message",
                                                    {"content": msg.content, "messageType": "body"})
                        else:
                            msg = messages[-1]
                            if isinstance(msg, AIMessage):
                                await websocket.send_json({"type": "typing"})
                                await asyncio.sleep(0.5)
                                await websocket.send_json({
                                    "type":        "ai_message",
                                    "content":     msg.content,
                                    "messageType": "intro",
                                })
                                await log_event(session_id, thread_id, node_name, "ai_message",
                                                {"content": msg.content, "messageType": "intro"})
 
        # ── MAIN WHILE LOOP ───────────────────────────────────────────────────
        while True:
 
            # Check if workflow completed
            snapshot = await graph_app.aget_state(config)
            if not snapshot.next:
                await websocket.send_json({"type": "workflow_complete"})
                await update_run_status(session_id, "completed", scoring_done=True)
                break
 
            data         = await websocket.receive_text()
            message_data = json.loads(data)
 
            if session_id in sessions:
                sessions[session_id]["last_activity"] = time.time()
 
            print(f"[DEBUG] Received message: {message_data}")
 
            # ── sync_state ────────────────────────────────────────────────────
            if message_data.get("type") == "sync_state":
                print("[SYNC] Client requested state sync after reconnection")
                current_state = await graph_app.aget_state(config)
                snapshot      = await graph_app.aget_state(config)
                next_nodes    = snapshot.next if snapshot else []
                print(f"[SYNC] Current next nodes: {next_nodes}")
                await websocket.send_json({
                    "type":        "state_synced",
                    "message":     "Connection restored. You can continue where you left off.",
                    "next_nodes":  next_nodes
                })
                continue
 
            # ── pong ──────────────────────────────────────────────────────────
            if message_data.get("type") == "pong":
                # print("[HEARTBEAT] Received pong from client")
                continue
 
            # ── ping ──────────────────────────────────────────────────────────
            if message_data.get("type") == "ping":
                # print("[HEARTBEAT] Received ping from client, sending pong")
                await websocket.send_json({"type": "pong"})
                continue
 
            # ── address_data ──────────────────────────────────────────────────
            if message_data.get("type") == "address_data":
                address_payload = message_data.get("data", {})
                print(f"Received address data: {address_payload}")
 
                current_state    = await graph_app.aget_state(config)
                current_messages = current_state.values.get("messages", [])
                import json as _json
                address_message  = _json.dumps(address_payload)
                display_address  = address_payload.get("full", address_payload.get("street", "Address received"))
 
                await graph_app.aupdate_state(config, {
                    "address":  address_payload,
                    "messages": current_messages + [HumanMessage(content=address_message)]
                })
                await log_event(session_id, thread_id, "store_address", "user_message",
                                {"content": f"Address: {display_address}"})
 
                async for event in graph_app.astream(None, config=config, stream_mode="updates"):
                    for node_name, node_data in event.items():
                        print(f"[DEBUG] Processing node: {node_name}")
                        await log_event(session_id, thread_id, node_name, "node_enter",
                                        {"state_keys": list(node_data.keys()) if node_data else []})
                        await process_node(node_name, node_data)
                continue
 
            # ── gps_data ──────────────────────────────────────────────────────
            if message_data.get("type") == "gps_data":
                gps_payload = message_data.get("data", {})
                print(f"Received GPS data: lat={gps_payload.get('lat')}, lng={gps_payload.get('lng')}")
 
                current_state    = await graph_app.aget_state(config)
                current_messages = current_state.values.get("messages", [])
                import json as _json
                gps_message = _json.dumps(gps_payload)
                raw_lat     = gps_payload.get("lat")
                raw_lng     = gps_payload.get("lng")
                gps_lat     = float(raw_lat) if raw_lat is not None else 0.0
                gps_lng     = float(raw_lng) if raw_lng is not None else 0.0
 
                await graph_app.aupdate_state(config, {
                    "gps_lat":  gps_lat,
                    "gps_lng":  gps_lng,
                    "messages": current_messages + [HumanMessage(content=gps_message)]
                })
                await log_event(session_id, thread_id, "process_gps", "user_message",
                                {"content": f"GPS: lat={gps_lat}, lng={gps_lng}"})
 
                async for event in graph_app.astream(None, config=config, stream_mode="updates"):
                    for node_name, node_data in event.items():
                        print(f"[DEBUG] Processing node: {node_name}")
                        await log_event(session_id, thread_id, node_name, "node_enter",
                                        {"state_keys": list(node_data.keys()) if node_data else []})
                        await process_node(node_name, node_data)
                continue
 
            # ── work_experience_data ──────────────────────────────────────────
            if message_data.get("type") == "work_experience_data":
                work_exp_data = message_data.get("data", [])
                print(f"Received work experiences: {work_exp_data}")
 
                current_state    = await graph_app.aget_state(config)
                current_messages = current_state.values.get("messages", [])
 
                if isinstance(work_exp_data, list):
                    experiences_text = ", ".join([
                        f"{exp['role']} at {exp['company']} ({exp['startDate']} to {exp['endDate']})"
                        for exp in work_exp_data
                    ])
                    work_exp_message = f"Work experience: {experiences_text}"
                else:
                    work_exp_message = f"Added: {work_exp_data['role']} at {work_exp_data['company']}"
 
                await graph_app.aupdate_state(config, {
                    "work_experience": work_exp_data if isinstance(work_exp_data, list) else [work_exp_data],
                    "messages":        current_messages + [HumanMessage(content=work_exp_message)]
                })
                await log_event(session_id, thread_id, "store_work_experience_response", "user_message",
                                {"content": work_exp_message})
 
                async for event in graph_app.astream(None, config=config, stream_mode="updates"):
                    for node_name, node_data in event.items():
                        print(f"[DEBUG] Processing node: {node_name}")
                        await log_event(session_id, thread_id, node_name, "node_enter",
                                        {"state_keys": list(node_data.keys()) if node_data else []})
                        await process_node(node_name, node_data)
                continue
 
            # ── skip non-user messages ────────────────────────────────────────
            if message_data.get("type") != "user_message":
                print(f"[DEBUG] Skipping non-user message type: {message_data.get('type')}")
                continue
 
            # ── user_message ──────────────────────────────────────────────────
            user_input = str(message_data.get("content") or "").strip()
            if not user_input:
                print("[DEBUG] Empty user input, skipping")
                continue

            # ── Stop command — end conversation immediately ───────────────────────────────
            if user_input.lower().strip(".,!?") in ("stop", "quit", "exit", "bye", "cancel", "i want to stop", "please stop"):
                print(f"[DEBUG] Stop command received — ending conversation")
                await websocket.send_json({"type": "typing"})
                await asyncio.sleep(0.5)
                await websocket.send_json({
                    "type":        "ai_message",
                    "content":     "No problem! You can come back and apply when you're ready. Good luck! 👋",
                    "messageType": "body"
                })
                await asyncio.sleep(0.8)
                await websocket.send_json({"type": "conversation_ended"})  # ← tells frontend not to reconnect
                await update_run_status(session_id, "completed")
                await websocket.close()
                break
            # ─────────────────────────────────────────────────────────────────────────────
 
            await log_event(session_id, thread_id, None, "user_message", {"content": user_input})
 
            current_state    = await graph_app.aget_state(config)
            current_messages = current_state.values.get("messages", [])
 
            await graph_app.aupdate_state(config, {
                "messages": current_messages + [HumanMessage(content=user_input)]
            })
 
            print("[DEBUG] Resuming workflow after user message")
 
            async for event in graph_app.astream(None, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    print(f"[DEBUG] Processing node: {node_name}")
                    await log_event(session_id, thread_id, node_name, "node_enter",
                                    {"state_keys": list(node_data.keys()) if node_data else []})
 
                    # Status tracking
                    if node_name == "summary":
                        await update_run_status(session_id, "completed", scoring_done=True)
                    if node_name == "evaluate_single_knockout" and node_data:
                        if node_data.get("current_knockout_failed", False):
                            await update_run_status(session_id, "completed", knockout_failed=True)
 
                    await process_node(node_name, node_data)
 
    except WebSocketDisconnect:
        print(f"Client disconnected: {session_id}")
        sessions[session_id]["active"] = False
        heartbeat_task.cancel()
        await update_run_status(session_id, "completed")
 
    except Exception as e:
        error_details = _tb.format_exc()
        print(f"Error in WebSocket: {e}")
        print(f"Full traceback:\n{error_details}")
        heartbeat_task.cancel()
        await log_error(session_id, thread_id, None, e)
        await update_run_status(session_id, "errored", error_detail=error_details[:2000])
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()
 
    finally:
        if not heartbeat_task.done():
            heartbeat_task.cancel()
 

# ══════════════════════════════════════════════════════════════════════════════
# ADMIN ROUTER
# ══════════════════════════════════════════════════════════════════════════════

# ADMIN_KEY = os.getenv("ADMIN_KEY", "cleo_admin_secret_change_me")
ADMIN_KEY = "admin_secret_key1234"

admin_key_header = APIKeyHeader(name="X-Admin-Key", auto_error=True)

async def verify_admin_key(key: str = Depends(admin_key_header)):
    if key != ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")

admin_router = APIRouter(prefix="/admin", dependencies=[Depends(verify_admin_key)])


# ── PII masking helpers ────────────────────────────────────────────────────────

def _mask_pii(text: str) -> str:
    if not text:
        return text
    text = _re.sub(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', '***@***.***', text)
    text = _re.sub(r'\+?[\d\s\-\(\)]{10,}', '***-***-****', text)
    return text

def _mask_event_pii(data: dict) -> dict:
    if not data:
        return data
    masked = dict(data)
    if "content" in masked:
        masked["content"] = _mask_pii(str(masked["content"]))
    return masked

def _mask_state_pii(state: dict) -> dict:
    masked = dict(state)
    pd = masked.get("personal_details", {})
    if pd:
        safe = dict(pd)
        if "email" in safe:
            safe["email"] = _mask_pii(safe["email"])
        if "phone" in safe:
            safe["phone"] = _mask_pii(safe["phone"])
        masked["personal_details"] = safe
    return masked

async def _get_log_conn():
    conn_str = os.getenv("POSTGRES_CONNECTION_STRING")
    return await AsyncConnection.connect(conn_str, autocommit=True, row_factory=dict_row)


# ── Admin endpoints ────────────────────────────────────────────────────────────

@admin_router.get("/runs")
async def list_runs(
    status: Optional[str] = None,
    job_type: Optional[str] = None,
    brand_name: Optional[str] = None,
    has_error: Optional[bool] = None,
    knockout_failed: Optional[bool] = None,
    scoring_done: Optional[bool] = None,
    from_ts: Optional[str] = None,
    to_ts: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    reveal_pii: bool = False,
):
    """Home screen: paginated runs list with filters."""
    conn = await _get_log_conn()
    try:
        conditions = []
        vals = []

        if status:
            conditions.append("status = %s"); vals.append(status)
        if job_type:
            conditions.append("job_type = %s"); vals.append(job_type)
        if brand_name:
            conditions.append("brand_name = %s"); vals.append(brand_name)
        if has_error is not None:
            conditions.append("has_error = %s"); vals.append(has_error)
        if knockout_failed is not None:
            conditions.append("knockout_failed = %s"); vals.append(knockout_failed)
        if scoring_done is not None:
            conditions.append("scoring_done = %s"); vals.append(scoring_done)
        if from_ts:
            conditions.append("started_at >= %s"); vals.append(from_ts)
        if to_ts:
            conditions.append("started_at <= %s"); vals.append(to_ts + "T23:59:59")
        if search:
            conditions.append("(thread_id ILIKE %s OR last_user_message ILIKE %s)")
            vals += [f"%{search}%", f"%{search}%"]

        where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
        count_vals = vals.copy()
        vals += [limit, offset]

        cur = await conn.execute(
            f"""SELECT session_id, thread_id, job_type, brand_name, location,
                       started_at, last_event_at, status, last_node,
                       last_user_message, has_error, knockout_failed,
                       scoring_done, error_detail
                FROM conversation_runs
                {where}
                ORDER BY started_at DESC
                LIMIT %s OFFSET %s;""",
            vals
        )
        rows = await cur.fetchall()

        result = []
        for r in rows:
            row = dict(r)
            if not reveal_pii and row.get("last_user_message"):
                row["last_user_message"] = _mask_pii(row["last_user_message"])
            result.append(row)

        cur = await conn.execute(
            f"SELECT COUNT(*) as total FROM conversation_runs {where};",
            count_vals
        )
        count_row = await cur.fetchone()
        return {"runs": result, "total": count_row["total"], "limit": limit, "offset": offset}
    finally:
        await conn.close()


@admin_router.get("/runs/{session_id}")
async def get_run_detail(session_id: str, reveal_pii: bool = False):
    """All events for one run + run metadata."""
    conn = await _get_log_conn()
    try:
        cur = await conn.execute(
            "SELECT * FROM conversation_runs WHERE session_id = %s;", [session_id]
        )
        run = await cur.fetchone()
        if not run:
            raise HTTPException(status_code=404, detail="Run not found")

        cur = await conn.execute(
            """SELECT id, node_name, event_type, event_data, timestamp
               FROM conversation_events
               WHERE session_id = %s
               ORDER BY timestamp ASC;""",
            [session_id]
        )
        events = await cur.fetchall()

        events_list = []
        for e in events:
            ev = dict(e)
            if not reveal_pii:
                ev["event_data"] = _mask_event_pii(ev.get("event_data", {}))
            events_list.append(ev)

        return {"run": dict(run), "events": events_list}
    finally:
        await conn.close()


@admin_router.get("/runs/{session_id}/state")
async def get_run_state(session_id: str, reveal_pii: bool = False):
    """Current LangGraph state for a run."""
    session = sessions.get(session_id)
    if not session:
        conn = await _get_log_conn()
        try:
            cur = await conn.execute(
                "SELECT thread_id FROM conversation_runs WHERE session_id = %s;", [session_id]
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            thread_id = row["thread_id"]
        finally:
            await conn.close()
    else:
        thread_id = session["thread_id"]

    cfg = {"configurable": {"thread_id": thread_id}}
    state = await graph_app.aget_state(cfg)
    if not state:
        raise HTTPException(status_code=404, detail="No state found")

    state_dict = dict(state.values)
    if not reveal_pii:
        state_dict = _mask_state_pii(state_dict)

    return {"state": state_dict, "next": list(state.next)}


@admin_router.get("/runs/{session_id}/state-diff")
async def get_state_diff(session_id: str):
    """Per-checkpoint state diffs — powers the right-pane diff view."""
    session = sessions.get(session_id)
    if not session:
        conn = await _get_log_conn()
        try:
            cur = await conn.execute(
                "SELECT thread_id FROM conversation_runs WHERE session_id = %s;", [session_id]
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            thread_id = row["thread_id"]
        finally:
            await conn.close()
    else:
        thread_id = session["thread_id"]

    cfg = {"configurable": {"thread_id": thread_id}}

    TRACKED_KEYS = [
        "current_question_index", "current_knockout_question_index",
        "knockout_passed", "current_knockout_failed",
        "email_verified", "phone_verified", "id_verified",
        "email_otp_attempts", "phone_otp_attempts",
        "email_attempt_count", "phone_attempt_count",
        "score", "total_score", "scores",
        "personal_details", "answers", "knockout_answers",
        "delay_node_type", "acknowledgement_type",
        "gps_verified", "gps_flagged", "address",
    ]

    history = []
    prev_vals = {}

    async for checkpoint in graph_app.aget_state_history(cfg):
        vals = dict(checkpoint.values)
        diff = {}
        for key in TRACKED_KEYS:
            if key in vals and vals[key] != prev_vals.get(key):
                diff[key] = {"before": prev_vals.get(key), "after": vals[key]}
        prev_vals = {k: vals.get(k) for k in TRACKED_KEYS}

        history.append({
            "checkpoint_id": str(checkpoint.config.get("configurable", {}).get("checkpoint_id", "")),
            "next": list(checkpoint.next),
            "diff": diff,
            "timestamp": checkpoint.metadata.get("created_at", ""),
        })

    history.reverse()
    return {"diffs": history}


@admin_router.get("/runs/{session_id}/checkpoints")
async def get_checkpoints(session_id: str):
    """Raw LangGraph checkpoint list for the flow navigator."""
    session = sessions.get(session_id)
    if not session:
        conn = await _get_log_conn()
        try:
            cur = await conn.execute(
                "SELECT thread_id FROM conversation_runs WHERE session_id = %s;", [session_id]
            )
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Session not found")
            thread_id = row["thread_id"]
        finally:
            await conn.close()
    else:
        thread_id = session["thread_id"]

    cfg = {"configurable": {"thread_id": thread_id}}
    checkpoints = []
    async for cp in graph_app.aget_state_history(cfg):
        checkpoints.append({
            "checkpoint_id": str(cp.config.get("configurable", {}).get("checkpoint_id", "")),
            "next": list(cp.next),
            "metadata": cp.metadata,
        })
    checkpoints.reverse()
    return {"checkpoints": checkpoints}


# ── Serve log viewer HTML ──────────────────────────────────────────────────────

@app.get("/admin/log-viewer")
async def serve_log_viewer():
    """Serve the admin log viewer UI — no auth (key is entered in the UI itself)"""
    return FileResponse("log_viewer.html", media_type="text/html",
                        headers={"Cache-Control": "no-store"})


# Register admin router
app.include_router(admin_router)


if __name__ == "__main__":
    import uvicorn
    # uvicorn.run(app, host="0.0.0.0", port=8000)
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)