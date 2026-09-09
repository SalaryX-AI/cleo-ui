"""
Interview Scheduling additions to main.py
Apply these 4 changes in order.
"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 1 — imports (top of file, after existing graph imports)
# ─────────────────────────────────────────────────────────────────────────────

# Find:
# from passport_graph import build_passport_graph, PassportState
# from passport_configs import PASSPORT_CONFIG

# Add after:
# from interview_graph import build_interview_graph, InterviewState

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2 — lifespan: initialise interview graph
# ─────────────────────────────────────────────────────────────────────────────

# Find:
# graph_app          = None
# passport_graph_app = None

# Replace with:
# graph_app           = None
# passport_graph_app  = None
# interview_graph_app = None

# Find:
# global graph_app, passport_graph_app
# graph_app          = build_graph(checkpointer)
# passport_graph_app = build_passport_graph(checkpointer)

# Replace with:
# global graph_app, passport_graph_app, interview_graph_app
# graph_app           = build_graph(checkpointer)
# passport_graph_app  = build_passport_graph(checkpointer)
# interview_graph_app = build_interview_graph(checkpointer)
# print("Job, Passport and Interview graphs initialized")

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 3 — /start-interview-session endpoint
# Add after /start-passport-session endpoint
# ─────────────────────────────────────────────────────────────────────────────

START_INTERVIEW_SESSION = """
@app.post("/start-interview-session")
async def start_interview_session(
    candidate_id: str  = Body(...),
    is_live:      bool = Body(default=False),
    api_key:      str  = Body(...),
):
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    session_id = str(uuid.uuid4())
    thread_id  = f"thread_interview_{session_id}"

    sessions[session_id] = {
        "thread_id":    thread_id,
        "job_type":     "interview",
        "candidate_id": candidate_id,
        "is_live":      is_live,
        "active":       True,
        "created_at":   time.time(),
        "last_activity": time.time(),
        # Filler fields expected by session cleanup
        "job_id":                "",
        "company_id":            "",
        "location":              "",
        "job_shift":             "",
        "brand_name":            "",
        "single_company":        False,
        "verification_required": False,
        "job_template_id":       "",
    }

    return {
        "session_id": session_id,
        "mode":       "interview",
    }
"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 4 — /interview/ws/{session_id} WebSocket endpoint
# Add after /passport/ws/{session_id} endpoint
# ─────────────────────────────────────────────────────────────────────────────

INTERVIEW_WEBSOCKET = """
@app.websocket("/interview/ws/{session_id}")
async def interview_websocket_endpoint(websocket: WebSocket, session_id: str):
    global interview_graph_app
    await websocket.accept()

    if session_id not in sessions:
        await websocket.send_json({"type": "error", "message": "Invalid session ID"})
        await websocket.close()
        return

    heartbeat_task = asyncio.create_task(websocket_heartbeat(websocket))

    session      = sessions[session_id]
    sessions[session_id]["websocket"] = websocket
    thread_id    = session["thread_id"]
    is_live      = session["is_live"]
    candidate_id = session["candidate_id"]

    config = {"configurable": {"thread_id": thread_id}}

    # Nodes that produce no new messages — skip streaming them
    SKIP_NODES = {
        "date_router", "slot_router", "confirmation_router",
        "post_schedule", "send_email",
    }

    try:
        # ── Reconnection check ────────────────────────────────────────────────
        existing_state = await interview_graph_app.aget_state(config)

        if existing_state.values and existing_state.values.get("messages"):
            print(f"[INTERVIEW RECONNECT] Existing state for {session_id}")
        else:
            # ── New session ───────────────────────────────────────────────────
            print(f"[INTERVIEW NEW SESSION] Starting for {session_id}")

            initial_state = InterviewState(
                messages            = [],
                session_id          = session_id,
                is_live             = is_live,
                candidate_id        = candidate_id,
                candidate_name      = "",
                candidate_email     = "",
                candidate_phone     = "",
                candidate_state     = "",
                interview_dates     = [],
                interview_duration  = 30,
                availability        = [],
                google_auth_token   = "",
                hiring_manager_id   = "",
                hiring_manager      = "",
                timezone            = "America/New_York",
                booked_slots        = [],
                selected_date       = "",
                available_slots     = [],
                selected_slot       = "",
                confirmed           = False,
                event_id            = "",
                email_sent          = False,
                completed           = False,
                re_ask_attempts     = {},
            )

            async for event in interview_graph_app.astream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    print(f"[INTERVIEW NODE] {node_name}")

                    if node_name in SKIP_NODES:
                        continue

                    if node_data and "messages" in node_data:
                        for msg in node_data["messages"]:
                            if isinstance(msg, AIMessage):
                                await websocket.send_json({"type": "typing"})
                                await asyncio.sleep(0.8)
                                await asyncio.sleep(0.7)
                                await websocket.send_json({
                                    "type":        "ai_message",
                                    "content":     msg.content,
                                    "messageType": "body",
                                })

        # ── Main message loop ─────────────────────────────────────────────────
        while True:

            snapshot = await interview_graph_app.aget_state(config)
            if not snapshot.next or snapshot.values.get("completed"):
                await websocket.send_json({"type": "workflow_complete"})
                break

            data         = await websocket.receive_text()
            message_data = json.loads(data)

            if session_id in sessions:
                sessions[session_id]["last_activity"] = time.time()

            print(f"[INTERVIEW WS] Received: {message_data}")

            # ── Heartbeat ─────────────────────────────────────────────────────
            if message_data.get("type") == "pong":
                continue
            if message_data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            # ── Sync state ────────────────────────────────────────────────────
            if message_data.get("type") == "sync_state":
                snapshot   = await interview_graph_app.aget_state(config)
                next_nodes = snapshot.next if snapshot else []
                await websocket.send_json({
                    "type":       "state_synced",
                    "message":    "Connection restored. You can continue where you left off.",
                    "next_nodes": next_nodes,
                })
                continue

            # ── Skip non-user messages ────────────────────────────────────────
            if message_data.get("type") != "user_message":
                print(f"[INTERVIEW WS] Skipping: {message_data.get('type')}")
                continue

            user_input = str(message_data.get("content") or "").strip()
            if not user_input:
                continue

            current_state    = await interview_graph_app.aget_state(config)
            current_messages = current_state.values.get("messages", [])

            await interview_graph_app.aupdate_state(
                config,
                {"messages": current_messages + [HumanMessage(content=user_input)]}
            )

            print(f"[INTERVIEW WS] Resuming workflow")

            async for event in interview_graph_app.astream(None, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    print(f"[INTERVIEW NODE] {node_name}")

                    if node_name in SKIP_NODES:
                        continue

                    if node_data and "messages" in node_data:
                        messages = node_data["messages"]
                        # For final node send all messages (could be multiple)
                        msgs_to_send = messages[-2:] if node_name == "greeting" else messages[-1:]
                        for msg in msgs_to_send:
                            if isinstance(msg, AIMessage):
                                await websocket.send_json({"type": "typing"})
                                await asyncio.sleep(0.7)
                                await websocket.send_json({
                                    "type":        "ai_message",
                                    "content":     msg.content,
                                    "messageType": "body",
                                })

    except WebSocketDisconnect:
        print(f"[INTERVIEW WS] Client disconnected: {session_id}")
        sessions[session_id]["active"] = False
        heartbeat_task.cancel()

    except Exception as e:
        import traceback
        print(f"[INTERVIEW WS] Error: {e}")
        print(traceback.format_exc())
        heartbeat_task.cancel()
        await websocket.send_json({"type": "error", "message": str(e)})
        await websocket.close()

    finally:
        if not heartbeat_task.done():
            heartbeat_task.cancel()
"""
