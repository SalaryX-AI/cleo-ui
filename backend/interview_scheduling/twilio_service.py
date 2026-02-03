"""Twilio service for SMS sending and receiving"""

import os
from twilio.rest import Client
from twilio.request_validator import RequestValidator
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")


def send_sms(to_phone: str, message: str) -> bool:
    """
    Send SMS via Twilio
    
    Args:
        to_phone: Recipient phone number (E.164 format)
        message: Message text to send
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
            print("ERROR: Twilio credentials not configured")
            return False
        
        # Initialize Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Send SMS
        twilio_message = client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=to_phone
        )
        
        print(f"SMS sent to {to_phone}: SID {twilio_message.sid}")
        return twilio_message.sid is not None
        
    except Exception as e:
        print
        print(f"Error sending SMS to {to_phone}: {e}")
        return False


def send_initial_scheduling_sms(
    phone: str, 
    name: str, 
    company: str, 
    slots_formatted: str
) -> bool:
    """
    Send initial interview scheduling SMS
    
    Args:
        phone: Applicant phone number
        name: Applicant name
        company: Company name
        slots_formatted: Pre-formatted slots string
        
    Returns:
        bool: True if sent successfully
    """
    message = f"""Hi {name}, this is Cleo from {company}. Thanks for completing your screening!
We'd love to schedule an interview. Here are our available times:

{slots_formatted}

Please reply with your preferred day and time."""
    
    return send_sms(phone, message)


def verify_twilio_signature(request_url: str, post_data: dict, signature: str) -> bool:
    """
    Verify that incoming webhook is actually from Twilio
    
    Args:
        request_url: Full URL of the webhook endpoint
        post_data: POST data from request
        signature: X-Twilio-Signature header value
        
    Returns:
        bool: True if signature is valid
    """
    try:
        if not TWILIO_AUTH_TOKEN:
            print("WARNING: Cannot verify Twilio signature - auth token not set")
            return True  # Allow in development
        
        validator = RequestValidator(TWILIO_AUTH_TOKEN)
        return validator.validate(request_url, post_data, signature)
        
    except Exception as e:
        print(f"Error verifying Twilio signature: {e}")
        return False


def send_confirmation_sms(
    phone: str,
    name: str,
    company: str,
    selected_date: str,
    selected_time: str
) -> bool:
    """
    Send final confirmation SMS after interview is scheduled
    
    Args:
        phone: Applicant phone number
        name: Applicant name
        company: Company name
        selected_date: Confirmed interview date
        selected_time: Confirmed interview time
        
    Returns:
        bool: True if sent successfully
    """
    message = f"""✓ Confirmed! Your interview is scheduled for {selected_date} at {selected_time}.

We'll call you at {phone}. Please have your phone nearby.

If you need to reschedule, reply to this message at least 2 hours before your interview.

Looking forward to speaking with you!
- The {company} Hiring Team"""
    
    return send_sms(phone, message)


def send_custom_request_acknowledgment(phone: str, company: str) -> bool:
    """
    Send acknowledgment when applicant requests custom time
    
    Args:
        phone: Applicant phone number
        company: Company name
        
    Returns:
        bool: True if sent successfully
    """
    message = f"""Got it! I'll check with our {company} team about your availability and get back to you within 24 hours.

Thanks for your patience!"""
    
    return send_sms(phone, message)


def send_error_message(phone: str) -> bool:
    """
    Send error message when system has trouble processing response
    
    Args:
        phone: Applicant phone number
        
    Returns:
        bool: True if sent successfully
    """
    message = """Sorry, I'm having trouble processing your response. Could you please reply with:

1. The day you prefer
2. The time you prefer

Example: "Tuesday at 2:00 PM"

Or reply HELP to speak with someone directly."""
    
    return send_sms(phone, message)


def extract_sms_data(form_data: dict) -> tuple[str, str]:
    """
    Extract phone number and message from Twilio webhook data
    
    Args:
        form_data: Form data from Twilio webhook
        
    Returns:
        tuple: (from_phone, message_body)
    """
    from_phone = form_data.get('From', '')
    message_body = form_data.get('Body', '').strip()
    
    return from_phone, message_body
