"""
Passport additions to main.py
Apply these 4 changes in order.
"""

# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 1 — imports (top of file, after existing graph imports)
# ─────────────────────────────────────────────────────────────────────────────

# Find:
from graph import build_graph, ChatbotState

# Replace with:
from graph import build_graph, ChatbotState
from passport_graph import build_passport_graph, PassportState
from passport_configs import PASSPORT_CONFIG


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 2 — lifespan: initialise passport graph alongside job graph
# ─────────────────────────────────────────────────────────────────────────────

# Find:
"""
graph_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_app
"""

# Replace with:
"""
graph_app          = None
passport_graph_app = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global graph_app, passport_graph_app
"""

# Find:
"""
    # Build graph with checkpointer
    graph_app = build_graph(checkpointer)
    print("Graph initialized with AsyncPostgresSaver")
"""

# Replace with:
"""
    # Build graphs with checkpointer
    graph_app          = build_graph(checkpointer)
    passport_graph_app = build_passport_graph(checkpointer)
    print("Job graph and Passport graph initialized with AsyncPostgresSaver")
"""


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 3 — /start-passport-session endpoint
# Add this right after the existing /start-session endpoint (line ~272)
# ─────────────────────────────────────────────────────────────────────────────

NEW_ENDPOINT = """
@app.post("/start-passport-session")
async def start_passport_session(
    api_key:  str  = Query(...),
    is_live:  bool = Query(default=False),
):
    \"\"\"Create a new Cleo Work Passport™ session.\"\"\"

    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")

    session_id = str(uuid.uuid4())
    thread_id  = f"thread_passport_{session_id}"

    sessions[session_id] = {
        "thread_id":   thread_id,
        "job_type":    "passport",
        "location":    "",
        "job_id":      "",
        "company_id":  "",
        "is_live":     is_live,
        "active":      True,
        "created_at":  time.time(),
        "last_activity": time.time(),
    }

    return {
        "session_id": session_id,
        "mode":       "passport",
    }
"""


# ─────────────────────────────────────────────────────────────────────────────
# CHANGE 4 — /passport/ws/{session_id} WebSocket endpoint
# Add this right after the existing /ws/{session_id} endpoint
# ─────────────────────────────────────────────────────────────────────────────

PASSPORT_WEBSOCKET = """
@app.websocket("/passport/ws/{session_id}")
async def passport_websocket_endpoint(websocket: WebSocket, session_id: str):
    \"\"\"WebSocket connection for Cleo Work Passport™ flow.\"\"\"
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
            )

            # Stream initial graph run (greeting bubbles)
            async for event in passport_graph_app.astream(initial_state, config=config, stream_mode="updates"):
                for node_name, node_data in event.items():
                    if node_data and "messages" in node_data:
                        messages = node_data["messages"]

                        # Greeting: send all 3 bubbles with stagger
                        if node_name == "passport_greeting":
                            for msg in messages[-3:]:
                                if isinstance(msg, AIMessage):
                                    await websocket.send_json({"type": "typing"})
                                    await asyncio.sleep(0.8)
                                    await asyncio.sleep(1.2)
                                    await websocket.send_json({
                                        "type":        "ai_message",
                                        "content":     msg.content,
                                        "messageType": "intro",
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
"""