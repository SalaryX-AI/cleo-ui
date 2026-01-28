"""FastAPI application for interview scheduling system"""

import os
from fastapi import FastAPI, HTTPException, Request, Form, Header
from fastapi.responses import Response, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from dotenv import load_dotenv

from models import (
    SchedulingRequest,
    SchedulingResponse,
    SchedulingStatusResponse
)
from scheduling_service import (
    create_scheduling_session,
    get_session_by_phone,
    get_session_by_id,
    handle_scheduling_response
)
from twilio_service import (
    send_initial_scheduling_sms,
    extract_sms_data,
    verify_twilio_signature,
    send_error_message
)
from scheduling_prompts import format_slots_for_display

load_dotenv()

# Database connection
db_conn = None

# API Key for authentication
API_KEY = os.getenv("SCHEDULING_API_KEY", "scheduling_key_secure_456")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage database connection lifecycle"""
    global db_conn
    
    # Get connection string
    connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
    if not connection_string:
        raise ValueError("POSTGRES_CONNECTION_STRING not set")
    
    # Create async connection
    db_conn = await AsyncConnection.connect(
        connection_string,
        autocommit=True,
        row_factory=dict_row
    )
    
    print("✓ Database connection established")
    
    yield
    
    # Cleanup
    await db_conn.close()
    print("✓ Database connection closed")


# Initialize FastAPI app
app = FastAPI(
    title="Interview Scheduling API",
    description="SMS-based interview scheduling system",
    version="1.0.0",
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==================== ENDPOINTS ====================

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "service": "Interview Scheduling API",
        "status": "running",
        "version": "1.0.0"
    }


@app.post("/api/schedule-interview", response_model=SchedulingResponse)
async def initiate_scheduling(
    request: SchedulingRequest,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """
    Initiate interview scheduling process
    
    This endpoint:
    1. Validates the request
    2. Creates a scheduling session in database
    3. Sends initial SMS to applicant with available slots
    4. Returns session ID for tracking
    
    Args:
        request: SchedulingRequest with applicant details and slots
        x_api_key: API key for authentication
        
    Returns:
        SchedulingResponse with session_id and status
    """
    # Validate API key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    try:
        # Create session in database
        session_id = await create_scheduling_session(
            conn=db_conn,
            applicant_name=request.applicant_name,
            applicant_phone=request.applicant_phone,
            company_name=request.company_name,
            position=request.position,
            job_id=request.job_id,              
            candidate_id=request.candidate_id,  
            location=request.location, 
            available_slots=request.slots
        )
        
        # Format slots for SMS
        slots_formatted = format_slots_for_display(request.slots)
        
        # Send initial SMS
        sms_sent = send_initial_scheduling_sms(
            phone=request.applicant_phone,
            name=request.applicant_name,
            company=request.company_name,
            slots_formatted=slots_formatted
        )
        
        if not sms_sent:
            raise HTTPException(
                status_code=500,
                detail="Failed to send initial SMS"
            )
        
        return SchedulingResponse(
            session_id=session_id,
            status="initiated",
            message=f"Interview scheduling initiated for {request.applicant_name}"
        )
        
    except Exception as e:
        print(f"✗ Error initiating scheduling: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to initiate scheduling: {str(e)}"
        )


@app.post("/twilio/scheduling-webhook")
async def handle_incoming_sms(
    request: Request,
    From: str = Form(...),
    Body: str = Form(...),
    x_twilio_signature: str = Header(None, alias="X-Twilio-Signature")
):
    """
    Webhook endpoint for incoming SMS from Twilio
    
    This endpoint:
    1. Validates the request is from Twilio
    2. Looks up the scheduling session by phone number
    3. Processes the message with LLM
    4. Sends appropriate response via SMS
    5. Updates database with conversation and status
    
    Args:
        request: FastAPI request object
        From: Sender phone number (from Twilio)
        Body: Message content (from Twilio)
        x_twilio_signature: Twilio signature for validation
        
    Returns:
        Empty response (Twilio doesn't need response content)
    """
    try:
        # Get form data for signature verification
        form_data = await request.form()
        
        # Verify Twilio signature (security)
        request_url = str(request.url)
        is_valid = verify_twilio_signature(
            request_url,
            dict(form_data),
            x_twilio_signature or ""
        )
        
        if not is_valid:
            print("✗ Invalid Twilio signature")
            raise HTTPException(status_code=403, detail="Invalid signature")
        
        # Extract data
        from_phone = From
        message_body = Body.strip()
        
        print(f"\n{'='*60}")
        print(f"INCOMING SMS")
        print(f"From: {from_phone}")
        print(f"Message: {message_body}")
        print(f"{'='*60}\n")
        
        # Look up session by phone number
        session_data = await get_session_by_phone(db_conn, from_phone)
        
        if not session_data:
            print(f"✗ No session found for phone: {from_phone}")
            # Send error message
            send_error_message(from_phone)
            return Response(status_code=200)
        
        # Check if session is already completed
        if session_data.status == "confirmed":
            print(f"Session {session_data.session_id} already confirmed")
            return Response(status_code=200)
        
        # Process the message
        success = await handle_scheduling_response(
            conn=db_conn,
            session_data=session_data,
            applicant_message=message_body
        )
        
        if not success:
            print(f"✗ Failed to process message")
            send_error_message(from_phone)
        
        return Response(status_code=200)
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Error in webhook handler: {e}")
        import traceback
        traceback.print_exc()
        return Response(status_code=500)


@app.get("/api/scheduling-status/{session_id}", response_model=SchedulingStatusResponse)
async def get_scheduling_status(
    session_id: str,
    x_api_key: str = Header(..., alias="X-API-Key")
):
    """
    Check the status of a scheduling session
    
    Args:
        session_id: Session ID from initiate_scheduling response
        x_api_key: API key for authentication
        
    Returns:
        SchedulingStatusResponse with current session status
    """
    # Validate API key
    if x_api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    
    try:
        # Get session from database
        session_data = await get_session_by_id(db_conn, session_id)
        
        if not session_data:
            raise HTTPException(
                status_code=404,
                detail=f"Session not found: {session_id}"
            )
        
        # Get created_at and updated_at from database
        query = """
            SELECT created_at, updated_at 
            FROM interview_scheduling_sessions
            WHERE session_id = %s
        """
        
        async with db_conn.cursor() as cur:
            await cur.execute(query, (session_id,))
            row = await cur.fetchone()
        
        return SchedulingStatusResponse(
            session_id=session_data.session_id,
            status=session_data.status,
            applicant_name=session_data.applicant_name,
            company_name=session_data.company_name,
            position=session_data.position,
            selected_date=session_data.selected_date,
            selected_time=session_data.selected_time,
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"✗ Error getting status: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get status: {str(e)}"
        )


# ==================== ERROR HANDLERS ====================

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Custom HTTP exception handler"""
    return JSONResponse(                              
        status_code=exc.status_code,
        content={
            "error": exc.detail,
            "status_code": exc.status_code
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """General exception handler"""
    print(f"✗ Unhandled exception: {exc}")
    import traceback
    traceback.print_exc()
    
    return JSONResponse(                             
        status_code=500,
        content={
            "error": "Internal server error",
            "status_code": 500
        }
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "scheduling_api:app",
        host="0.0.0.0",
        port=8003,  # Different port from main Cleo app
        reload=True
    )
