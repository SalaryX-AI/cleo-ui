"""Xano integration for submitting confirmed interview schedules"""

import requests
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

# Xano API Configuration
XANO_API_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:NuFOC8Bg/PostInterviewfromAI " 
XANO_API_KEY = "sk_test_51QxA9F7C2E8B4D1A6F9C3E7B2A"


def submit_interview_to_xano(
    candidate_id: int,        
    job_id: str,             
    interview_date: str,     
    interview_time: str,     
    location: str,   
    interview_type: str = "Onsite",     
    meeting_link: str = ""                      
) -> bool:
    """
    Submit confirmed interview schedule to Xano
    
    Args:
        candidate_id: Candidate ID from your system
        job_id: Job ID
        interview_date: Selected interview date (e.g., "Tuesday, January 28, 2025")
        interview_time: Selected interview time (e.g., "2:00 PM")
        location: Interview location
        
    Returns:
        bool: True if submitted successfully, False otherwise
    """
    try:
        # Convert date format from "Tuesday, January 28, 2025" to "2025-01-28"
        from datetime import datetime
        
        # Parse the date string
        date_obj = datetime.strptime(interview_date, "%A, %B %d, %Y")
        formatted_date = date_obj.strftime("%Y-%m-%d")  # "2025-01-28"
        
        # Prepare payload matching Xano structure
        payload = {
            "Date": formatted_date,                    # "2025-01-28"
            "Candidate_id": candidate_id,              # candidate ID
            "Time": interview_time,                    # "2:00 PM"
            "Meeting_Link": "",                        # Static/empty
            "interview_held": False,                   # Static
            "Type": "Onsite",                          # Static
            "job_id": job_id,                          # job ID
            "Location": location                       # Interview location
        }
        
        # Prepare headers
        headers = {
            "Content-Type": "application/json"
        }
        
        if XANO_API_KEY:
            headers["x-api-key"] = XANO_API_KEY
        
        print(f"Submitting interview to Xano for candidate: {candidate_id}...")
        print(f"Payload: {payload}")
        
        # Send POST request
        response = requests.post(
            XANO_API_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✓ Successfully submitted interview to Xano: Candidate {candidate_id} - {formatted_date} at {interview_time}")
            return True
        else:
            print(f"✗ Failed to submit to Xano: {response.status_code} - {response.text}")
            return False
            
    except requests.exceptions.Timeout:
        print(f"✗ Xano API timeout for candidate {candidate_id}")
        return False
    except requests.exceptions.RequestException as e:
        print(f"✗ Error submitting to Xano: {e}")
        return False
    except Exception as e:
        print(f"✗ Unexpected error submitting to Xano: {e}")
        return False


def submit_with_retry(
    candidate_id: int,       
    job_id: str,            
    interview_date: str,    
    interview_time: str,    
    location: str,          
    interview_type: str = "Onsite",     
    meeting_link: str = "",             
    max_retries: int = 3
) -> bool:
    """
    Submit to Xano with retry logic (exponential backoff)
    
    Args:
        candidate_id: Candidate ID
        job_id: Job ID
        interview_date: Interview date
        interview_time: Interview time
        location: Interview location
        max_retries: Maximum number of retry attempts
        
    Returns:
        bool: True if submitted successfully within retry attempts
    """
    import time
    
    for attempt in range(1, max_retries + 1):
        print(f"Xano submission attempt {attempt}/{max_retries}...")
        
        success = submit_interview_to_xano(
            candidate_id=candidate_id,     
            job_id=job_id,                
            interview_date=interview_date,
            interview_time=interview_time,
            location=location,
            interview_type=interview_type,      
            meeting_link=meeting_link                       
        )
        
        if success:
            return True
        
        if attempt < max_retries:
            # Exponential backoff: 2^attempt seconds
            wait_time = 2 ** attempt
            print(f"Retrying in {wait_time} seconds...")
            time.sleep(wait_time)
    
    print(f"✗ Failed to submit to Xano after {max_retries} attempts")
    return False


def notify_custom_availability_request(
    applicant_name: str,
    applicant_phone: str,
    company_name: str,
    position: str,
    requested_times: str,
    session_id: str
) -> bool:
    """
    Notify Xano when applicant requests custom availability
    (not from available slots)
    
    Args:
        applicant_name: Full name
        applicant_phone: Phone number
        company_name: Company name
        position: Job position
        requested_times: What the applicant requested
        session_id: Session ID
        
    Returns:
        bool: True if notification sent successfully
    """
    try:
        payload = {
            "applicant_name": applicant_name,
            "applicant_phone": applicant_phone,
            "company_name": company_name,
            "position": position,
            "requested_availability": requested_times,
            "session_id": session_id,
            "request_type": "custom_availability",
            "created_at": datetime.now().isoformat()
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        if XANO_API_KEY:
            headers["x-api-key"] = XANO_API_KEY
        
        # Use same endpoint or a different one for custom requests
        response = requests.post(
            XANO_API_URL,
            json=payload,
            headers=headers,
            timeout=10
        )
        
        if response.status_code in [200, 201]:
            print(f"✓ Custom availability request sent to Xano for {applicant_name}")
            return True
        else:
            print(f"✗ Failed to send custom request to Xano: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"✗ Error sending custom request to Xano: {e}")
        return False