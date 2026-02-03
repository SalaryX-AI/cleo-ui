"""Core scheduling service - handles database operations and LLM processing"""

import json
import uuid
from datetime import datetime
from typing import Optional, Dict, List
import asyncio
from psycopg import AsyncConnection
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage

from scheduling_prompts import SCHEDULING_SYSTEM_PROMPT, format_slots_for_display
from models import LLMResponse, SessionData
from twilio_service import send_initial_scheduling_sms, send_confirmation_sms, send_sms
from xano_integration import submit_with_retry, notify_custom_availability_request


# Initialize LLM
llm = ChatOpenAI(
    model="gpt-4o-mini",
    temperature=0.3,
    model_kwargs={"response_format": {"type": "json_object"}}
)


async def create_scheduling_session(
    conn: AsyncConnection,
    applicant_name: str,
    applicant_phone: str,
    company_name: str,
    position: str,
    job_id: str,           
    candidate_id: int,    
    location: str,  
    interview_type: str,     
    meeting_link: str,       
    available_slots: dict
) -> str:
    """
    Create a new scheduling session in database
    
    Args:
        conn: Database connection
        applicant_name: Full name
        applicant_phone: Phone number (E.164 format)
        company_name: Company name
        position: Job position
        available_slots: Dict of available interview slots
        
    Returns:
        str: Session ID
    """
    session_id = f"sched_{uuid.uuid4().hex[:12]}"
    
    query = """
        INSERT INTO interview_scheduling_sessions 
        (session_id, applicant_name, applicant_phone, company_name, position, 
        job_id, candidate_id, location, interview_type, meeting_link, 
        available_slots, status)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING session_id
    """
    
    async with conn.cursor() as cur:
        await cur.execute(
            query,
            (
                session_id,                     
                applicant_name,                
                applicant_phone,               
                company_name,                  
                position,                      
                job_id,                        
                candidate_id,                  
                location,      
                interview_type,                
                meeting_link,                   
                json.dumps(available_slots),   
                'pending'                      
            )
        )
        result = await cur.fetchone()
    
    print(f"✓ Created scheduling session: {session_id}")
    return result['session_id']


async def get_session_by_phone(conn: AsyncConnection, phone: str) -> Optional[SessionData]:
    """
    Retrieve session by phone number
    
    Args:
        conn: Database connection
        phone: Applicant phone number
        
    Returns:
        SessionData or None
    """
    query = """
        SELECT * FROM interview_scheduling_sessions
        WHERE applicant_phone = %s
        ORDER BY created_at DESC
        LIMIT 1
    """
    
    async with conn.cursor() as cur:
        await cur.execute(query, (phone,))
        row = await cur.fetchone()
    
    if not row:
        return None
    
    return SessionData(
        session_id=row['session_id'],
        applicant_name=row['applicant_name'],
        applicant_phone=row['applicant_phone'],
        company_name=row['company_name'],
        position=row['position'],
        job_id=row['job_id'],              
        candidate_id=row['candidate_id'],  
        location=row['location'],          
        interview_type=row['interview_type'],      
        meeting_link=row['meeting_link'],          
        available_slots=row['available_slots'],
        conversation_history=row['conversation_history'] or [],
        selected_date=row['selected_date'],
        selected_time=row['selected_time'],
        status=row['status']
    )


async def get_session_by_id(conn: AsyncConnection, session_id: str) -> Optional[SessionData]:
    """
    Retrieve session by session ID
    
    Args:
        conn: Database connection
        session_id: Session ID
        
    Returns:
        SessionData or None
    """
    query = """
        SELECT * FROM interview_scheduling_sessions
        WHERE session_id = %s
    """
    
    async with conn.cursor() as cur:
        await cur.execute(query, (session_id,))
        row = await cur.fetchone()
    
    if not row:
        return None
    
    return SessionData(
        session_id=row['session_id'],
        applicant_name=row['applicant_name'],
        applicant_phone=row['applicant_phone'],
        company_name=row['company_name'],
        position=row['position'],
        job_id=row['job_id'],              
        candidate_id=row['candidate_id'],  
        location=row['location'],         
        interview_type=row['interview_type'],      
        meeting_link=row['meeting_link'],          
        available_slots=row['available_slots'],
        conversation_history=row['conversation_history'] or [],
        selected_date=row['selected_date'],
        selected_time=row['selected_time'],
        status=row['status']
    )


async def update_conversation_history(
    conn: AsyncConnection,
    session_id: str,
    role: str,
    message: str
):
    """
    Add message to conversation history
    
    Args:
        conn: Database connection
        session_id: Session ID
        role: 'assistant' or 'applicant'
        message: Message content
    """
    timestamp = datetime.now().isoformat()
    
    query = """
        UPDATE interview_scheduling_sessions
        SET conversation_history = conversation_history || %s::jsonb
        WHERE session_id = %s
    """
    
    new_message = json.dumps([{
        "role": role,
        "message": message,
        "timestamp": timestamp
    }])
    
    async with conn.cursor() as cur:
        await cur.execute(query, (new_message, session_id))
    
    print(f"✓ Updated conversation for {session_id}: [{role}] {message[:50]}...")


async def update_session_status(
    conn: AsyncConnection,
    session_id: str,
    status: str,
    selected_date: Optional[str] = None,
    selected_time: Optional[str] = None
):
    """
    Update session status and optionally set selected date/time
    
    Args:
        conn: Database connection
        session_id: Session ID
        status: New status
        selected_date: Selected interview date (optional)
        selected_time: Selected interview time (optional)
    """
    query = """
        UPDATE interview_scheduling_sessions
        SET status = %s, selected_date = %s, selected_time = %s
        WHERE session_id = %s
    """
    
    async with conn.cursor() as cur:
        await cur.execute(query, (status, selected_date, selected_time, session_id))
    
    print(f"✓ Updated session {session_id}: status={status}, date={selected_date}, time={selected_time}")


def process_with_llm(
    applicant_name: str,
    company_name: str,
    position: str,
    available_slots: dict,
    conversation_history: List[dict],
    latest_message: str
) -> LLMResponse:
    """
    Process applicant message using LLM
    
    Args:
        applicant_name: Applicant's name
        company_name: Company name
        position: Job position
        available_slots: Available interview slots
        conversation_history: Previous conversation messages
        latest_message: Latest message from applicant
        
    Returns:
        LLMResponse: Parsed LLM response
    """
    # Format conversation history for prompt
    history_text = ""
    for msg in conversation_history[-5:]:  # Last 5 messages for context
        role = msg.get('role', 'unknown')
        content = msg.get('message', '')
        timestamp = msg.get('timestamp', '')
        history_text += f"[{role.upper()}] {content}\n"
    
    if not history_text:
        history_text = "No previous conversation"
    
    # Format available slots as JSON
    slots_json = json.dumps(available_slots, indent=2)
    
    # Build prompt
    prompt = SCHEDULING_SYSTEM_PROMPT.format(
        applicant_name=applicant_name,
        company_name=company_name,
        position=position,
        available_slots_json=slots_json,
        conversation_history=history_text,
        latest_message=latest_message
    )
    
    print(f"\n{'='*60}")
    print("LLM INPUT:")
    print(f"Applicant: {applicant_name}")
    print(f"Latest message: {latest_message}")
    print(f"{'='*60}\n")
    
    try:
        # Call LLM
        response = llm.invoke([HumanMessage(content=prompt)])
        response_text = response.content.strip()
        
        print(f"\n{'='*60}")
        print("LLM OUTPUT:")
        print(response_text)
        print(f"{'='*60}\n")
        
        # Parse JSON response
        llm_data = json.loads(response_text)
        
        # Validate and create LLMResponse object
        llm_response = LLMResponse(**llm_data)
        
        return llm_response
        
    except json.JSONDecodeError as e:
        print(f"✗ Error parsing LLM response as JSON: {e}")
        print(f"Raw response: {response_text}")
        
        # Return fallback response
        return LLMResponse(
            analysis={
                "intent": "other",
                "selected_date": None,
                "selected_time": None,
                "is_valid_selection": False,
                "confidence": "low",
                "requires_confirmation": False
            },
            response_message="I'm having trouble understanding. Could you please reply with your preferred day and time from the options I shared?",
            action="continue_conversation",
            session_status="pending"
        )
    
    except Exception as e:
        print(f"✗ Error processing with LLM: {e}")
        
        # Return fallback response
        return LLMResponse(
            analysis={
                "intent": "other",
                "selected_date": None,
                "selected_time": None,
                "is_valid_selection": False,
                "confidence": "low",
                "requires_confirmation": False
            },
            response_message="Sorry, I'm having technical difficulties. Please try again or reply HELP.",
            action="continue_conversation",
            session_status="pending"
        )


async def handle_scheduling_response(
    conn: AsyncConnection,
    session_data: SessionData,
    applicant_message: str
) -> bool:
    """
    Handle incoming message from applicant
    
    Args:
        conn: Database connection
        session_data: Current session data
        applicant_message: Message from applicant
        
    Returns:
        bool: True if processed successfully
    """
    try:
        # Add applicant message to conversation history
        await update_conversation_history(
            conn,
            session_data.session_id,
            'applicant',
            applicant_message
        )
        
        # Process with LLM
        llm_response = process_with_llm(
            applicant_name=session_data.applicant_name,
            company_name=session_data.company_name,
            position=session_data.position,
            available_slots=session_data.available_slots,
            conversation_history=session_data.conversation_history,
            latest_message=applicant_message
        )
        
        # Send SMS reply
        send_sms(session_data.applicant_phone, llm_response.response_message)
        
        # Add assistant response to conversation history
        await update_conversation_history(
            conn,
            session_data.session_id,
            'assistant',
            llm_response.response_message
        )
        
        # Update session based on action
        if llm_response.action == "finalize":
            # Interview confirmed - update database
            await update_session_status(
                conn,
                session_data.session_id,
                'confirmed',
                llm_response.analysis.selected_date,
                llm_response.analysis.selected_time
            )
            
            # Submit to Xano
            submit_with_retry(
                candidate_id=session_data.candidate_id,        
                job_id=session_data.job_id,                   
                interview_date=llm_response.analysis.selected_date,
                interview_time=llm_response.analysis.selected_time,
                location=session_data.location,
                interview_type=session_data.interview_type,    
                meeting_link=session_data.meeting_link                
            )
            
        elif llm_response.action == "mark_custom_request":
            # Custom availability requested
            await update_session_status(
                conn,
                session_data.session_id,
                'custom_request'
            )
            
            # Notify Xano
            # notify_custom_availability_request(
            #     applicant_name=session_data.applicant_name,
            #     applicant_phone=session_data.applicant_phone,
            #     company_name=session_data.company_name,
            #     position=session_data.position,
            #     requested_times=applicant_message,
            #     session_id=session_data.session_id
            # )
            
        else:
            # Continue conversation - update status
            await update_session_status(
                conn,
                session_data.session_id,
                llm_response.session_status
            )
        
        return True
        
    except Exception as e:
        print(f"✗ Error handling scheduling response: {e}")
        return False
