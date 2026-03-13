"""OTP Service for Email and Phone Verification"""

import os
import random
import time
import requests
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
import plivo

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

# Brevo Configuration
BREVO_API_KEY = os.getenv("BREVO_API_KEY")
BREVO_FROM_EMAIL = os.getenv("BREVO_FROM_EMAIL")
BREVO_FROM_NAME = os.getenv("BREVO_FROM_NAME")

# Plivo Configuration
PLIVO_AUTH_ID = os.getenv("PLIVO_AUTH_ID")
PLIVO_AUTH_TOKEN = os.getenv("PLIVO_AUTH_TOKEN")
PLIVO_VERIFY_APP_UUID = os.getenv("PLIVO_VERIFY_APP_UUID")

# OTP Configuration
OTP_EXPIRY_MINUTES_SMS = 4  # OTP expiry time in minutes
OTP_EXPIRY_MINUTES_Email = 15  # OTP expiry time in minutes


def generate_otp() -> str:
    """Generate a random 6-digit OTP code"""
    return str(random.randint(100000, 999999))

def generate_session_id() -> int:
    """Generate a random 3-digit id"""
    return random.randint(100, 999)


def send_email_otp(email: str, code: str, brand_name: str, user_name: str = "there") -> bool:
    """
    Send OTP code via email using Brevo
    
    Args:
        email: Recipient email address
        code: 6-digit OTP code
        brand_name: Brand name for email
        user_name: User's first name for personalization
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    
    print("send_email_otp function called...")

    try:
        if not BREVO_API_KEY:
            print("ERROR: BREVO_API_KEY not configured")
            return False
        
        # Brevo API endpoint
        url = "https://api.brevo.com/v3/smtp/email"
        
        # Request headers
        headers = {
            "accept": "application/json",
            "api-key": BREVO_API_KEY,
            "content-type": "application/json"
        }
        
        # Email HTML content
        html_content = f"""
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px;">
            <h2 style="color: #667eea;">{brand_name} Application</h2>
            <p>Hi {user_name},</p>
            <p>Thank you for applying! Here's your verification code:</p>
            <div style="background: #f3f4f6; padding: 20px; border-radius: 8px; text-align: center; margin: 20px 0;">
                <h1 style="color: #667eea; font-size: 36px; letter-spacing: 8px; margin: 0;">{code}</h1>
            </div>
            <p>This code will expire in {OTP_EXPIRY_MINUTES_Email} minutes.</p>
            <p>If you didn't request this code, please ignore this email.</p>
            <br>
            <p style="color: #666; font-size: 12px;">Best regards,<br>{brand_name} Hiring Team</p>
        </div>
        """
        
        # Request payload
        payload = {
            "sender": {
                "name": BREVO_FROM_NAME,
                "email": BREVO_FROM_EMAIL
            },
            "to": [
                {
                    "email": email,
                    "name": user_name
                }
            ],
            "subject": f"Your {brand_name} Verification Code",
            "htmlContent": html_content
        }
        
        # Send email via Brevo API
        response = requests.post(url, json=payload, headers=headers)
        
        if response.status_code == 201:
            print(f"Email OTP sent to {email} via Brevo: Status {response.status_code}")
            return True
        else:
            print(f"Failed to send email via Brevo: {response.status_code} - {response.text}")
            return False
        
    except Exception as e:
        print(f"Error sending email OTP via Brevo: {e}")
        return False



def create_phone_verify_session(phone: str) -> str | None:
    """
    Create a Plivo Verify session which generates and sends OTP via SMS.

    Returns:
        session_uuid (str) if successful, None if failed
    """
    try:
        if not PLIVO_AUTH_ID or not PLIVO_AUTH_TOKEN or not PLIVO_VERIFY_APP_UUID:
            print("ERROR: Plivo Verify credentials not configured")
            return None

        client = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)

        response = client.verify_session.create(
            recipient=phone,
            app_uuid=PLIVO_VERIFY_APP_UUID,
            channel='sms'
        )

        session_uuid = response.session_uuid
        print(f"Plivo Verify session created: {session_uuid}")
        return session_uuid

    except Exception as e:
        print(f"Error creating Plivo Verify session: {e}")
        return None



def validate_phone_otp(session_uuid: str, otp: str) -> tuple[bool, str]:
    """
    Validate OTP entered by user against the Plivo Verify session.

    Returns:
        (True, "") on success
        (False, "incorrect") if OTP is wrong
        (False, "expired") if session expired
        (False, "error") on unexpected failure
    """
    try:
        client = plivo.RestClient(PLIVO_AUTH_ID, PLIVO_AUTH_TOKEN)

        response = client.verify_session.validate(
            session_uuid=session_uuid,
            otp=otp
        )

        print(f"Plivo Verify response: {response.message}")

        if response.message and "validated" in response.message.lower():
            return True, ""
        else:
            return False, "incorrect"

    except plivo.exceptions.PlivoRestError as e:
        error_msg = str(e).lower()
        print(f"Plivo Verify error: {e}")

        if "expired" in error_msg:
            return False, "expired"
        elif "invalid" in error_msg or "failed" in error_msg or "incorrect" in error_msg or "wrong" in error_msg:
            return False, "incorrect"
        else:
            return False, "error"

    except Exception as e:
        print(f"Unexpected error validating OTP: {e}")
        return False, "error"


def is_otp_expired(timestamp: float, otp_channel: str) -> bool:
    """
    Check if OTP has expired
    
    Args:
        timestamp: Unix timestamp when OTP was generated
        
    Returns:
        bool: True if expired, False otherwise
    """
    if timestamp == 0:
        return True
    
    current_time = time.time()
    elapsed_minutes = (current_time - timestamp) / 60

    if otp_channel == "phone":
        return elapsed_minutes > OTP_EXPIRY_MINUTES_SMS
    
    return elapsed_minutes > OTP_EXPIRY_MINUTES_Email


def verify_otp(user_input: str, stored_code: str, timestamp: float, otp_channel: str) -> tuple[bool, str]:
    """
    Verify OTP code
    
    Args:
        user_input: Code entered by user
        stored_code: Correct OTP code
        timestamp: When OTP was generated
        
    Returns:
        tuple: (is_valid, error_message)
    """
    # Check if OTP expired
    if is_otp_expired(timestamp, otp_channel):
        return False, "expired"
    
    # Clean user input
    user_input_clean = user_input.strip().replace(" ", "").replace("-", "")
    
    # Check if correct format
    if not user_input_clean.isdigit() or len(user_input_clean) != 6:
        return False, "invalid_format"
    
    # Check if matches
    if user_input_clean == stored_code:
        return True, ""
    
    return False, "incorrect"


