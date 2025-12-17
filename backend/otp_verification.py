"""OTP Service for Email and Phone Verification"""

import os
import random
import time
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
from twilio.rest import Client
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

# SendGrid Configuration
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL")

# Twilio Configuration
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

# OTP Configuration
# OTP_EXPIRY_MINUTES = 2  # OTP expiry time in minutes
OTP_EXPIRY_MINUTES_SMS = 4  # OTP expiry time in minutes
OTP_EXPIRY_MINUTES_Email = 15  # OTP expiry time in minutes


def generate_otp() -> str:
    """Generate a random 6-digit OTP code"""
    return str(random.randint(100000, 999999))


def send_email_otp(email: str, code: str, brand_name: str, user_name: str = "there") -> bool:
    """
    Send OTP code via email using SendGrid
    
    Args:
        email: Recipient email address
        code: 6-digit OTP code
        user_name: User's first name for personalization
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        if not SENDGRID_API_KEY:
            print("ERROR: SENDGRID_API_KEY not configured")
            return False
        
        # Create email message
        message = Mail(
            from_email=SENDGRID_FROM_EMAIL,
            to_emails=email,
            subject=f'Your {brand_name} Verification Code',
            html_content=f"""
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
        )
        
        # Send email
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        print(f"Email OTP sent to {email}: Status {response.status_code}")
        return response.status_code in [200, 201, 202]
        
    except Exception as e:
        print(f"Error sending email OTP: {e}")
        return False


def send_sms_otp(phone: str, code: str, brand_name: str) -> bool:
    """
    Send OTP code via SMS using Twilio
    
    Args:
        phone: Recipient phone number (E.164 format recommended)
        E.164 = +[CountryCode][Number with no leading zero]
        code: 6-digit OTP code
        
    Returns:
        bool: True if sent successfully, False otherwise
    """
    try:
        if not TWILIO_ACCOUNT_SID or not TWILIO_AUTH_TOKEN or not TWILIO_PHONE_NUMBER:
            print("ERROR: Twilio credentials not configured")
            return False
        
        # Initialize Twilio client
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Format message
        message_body = f"Your {brand_name} verification code is: {code}\n\nThis code expires in {OTP_EXPIRY_MINUTES_SMS} minutes."
        
        # Send SMS
        message = client.messages.create(
            body=message_body,
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )
        
        print(f"SMS OTP sent to {phone}: SID {message.sid}")
        return message.sid is not None
        
    except Exception as e:
        print(f"Error sending SMS OTP: {e}")
        return False


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


def extract_email_from_text(text: str) -> str:
    """Extract email address from natural language using LLM"""
    prompt = f"""Extract ONLY the email address from this text. 
    If no email is found, return 'NONE'.
    Return only the email address, nothing else.

    Text: "{text}"

    Email:"""
        
    response = llm.invoke(prompt)
    email = response.content.strip()
        
    # If LLM couldn't find email, return original text
    if email.upper() == "NONE" or email == "":
        return text.strip()
        
    return email



def extract_phone_from_text(text: str) -> str:
    """Extract phone number from natural language using LLM"""
    prompt = f"""Extract ONLY the phone number from this text.
    If no phone number is found, return 'NONE'.
    Return only the phone number, nothing else.

    Text: "{text}"

    Phone:"""
    
    response = llm.invoke(prompt)
    phone = response.content.strip()
    
    # If LLM couldn't find phone, return original text
    if phone.upper() == "NONE" or phone == "":
        return text.strip()
    
    return phone