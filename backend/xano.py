import requests
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
import json

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.units import inch
from io import BytesIO
from datetime import datetime

from dotenv import load_dotenv
import os

load_dotenv()

from prompts1 import GENERATE_JOB_CONFIG_PROMPT


# ==========================================================================================================
def send_applicant_to_xano(
    name: str,
    email: str,
    phone: str,
    score: float,
    max_score: float,
    json_report: dict,
    answers: dict,
    session_id: str,
):
    """
    Generate PDF and send applicant data to XANO
    """
    
    print(f"send_applicant_to_xano function called...")
    print(f"Applicant Name: {name}, Email: {email}, Phone: {phone}, Score: {score}, Max Score: {max_score}, Session ID: {session_id}")
    
    # Static company ID and job ID
    COMPANY_ID = "92b8f778-8b2f-4758-81d3-20c13d411334"  
    JOB_ID = "8ad4624e-9f8c-47f6-a449-5998af5c27fa"   
    
    XANO_API_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:6skoiMBa/candidate_new_api"

    # Add headers
    headers = {
            'x-api-key': 'sk_test_51QxA9F7C2E8B4D1A6F9C3E7B2A',
        }
    
    try:
        # Determine status
        status = "Short Listed" if score > 50 else "Rejected"

          # Generate PDF (using summary from JSON report)
        summary = json_report.get("fit_score", {}).get("explanation", "No summary available")
                
        # Generate PDF
        pdf_buffer = generate_applicant_pdf(
            name=name,
            email=email,
            phone=phone,
            score=score,
            max_score=max_score,
            summary=summary,
            answers=answers,
            status=status
        )
        
        # Prepare form data
        
        files = {
            'Report_pdf': ('applicant_report.pdf', pdf_buffer, 'application/pdf')
        }

        # Convert JSON report to string
        profile_summary_json = json.dumps(json_report, indent=2)
        
        data = {
            'Name': name,
            'Score': int(score),
            'Email': email,
            'Phone': phone,
            'job_id': JOB_ID,
            'company_id': COMPANY_ID,
            'Status': status,
            'ProfileSummary': profile_summary_json,
            'my_session_id': session_id,
            'Report_pdf': ('applicant_report.pdf', pdf_buffer, 'application/pdf')
        }

        # Send POST request
        response = requests.post(XANO_API_URL, data=data, headers=headers)
        
        if response.status_code == 200:
            print(f"Successfully sent applicant {name} to XANO")
            try:
                print(f"   Response: {response.json()}")
            except:
                print(f"   Response: {response.text}")
                return True

        else:
            print(f"Failed to send to XANO: {response.status_code}")
            print(f"   Response: {response.text}")
            return False
            
    except Exception as e:
            print(f"Error sending to XANO: {e}")
            import traceback
            traceback.print_exc()
            return False


def generate_applicant_pdf(
    name: str,
    email: str,
    phone: str,
    score: float,
    max_score: float,
    summary: str,
    answers: dict,
    status: str
) -> BytesIO:
    """
    Generate PDF report for applicant
    
    Returns:
        BytesIO: PDF file buffer
    """
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    
    # Title
    c.setFont("Helvetica-Bold", 20)
    c.drawString(1*inch, height - 1*inch, "Applicant Screening Report")
    
    # Date
    c.setFont("Helvetica", 10)
    c.drawString(1*inch, height - 1.3*inch, f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    
    # Applicant Info
    y = height - 2*inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, y, "Applicant Information")
    
    y -= 0.3*inch
    c.setFont("Helvetica", 11)
    c.drawString(1*inch, y, f"Name: {name}")
    
    y -= 0.25*inch
    c.drawString(1*inch, y, f"Email: {email}")
    
    y -= 0.25*inch
    c.drawString(1*inch, y, f"Phone: {phone}")
    
    # Score
    y -= 0.5*inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, y, "Screening Score")
    
    y -= 0.3*inch
    c.setFont("Helvetica", 11)
    percentage = (score / max_score * 100) if max_score > 0 else 0
    c.drawString(1*inch, y, f"Score: {score:.1f} / {max_score:.1f} ({percentage:.1f}%)")
    
    y -= 0.25*inch
    c.setFont("Helvetica-Bold", 11)
    c.drawString(1*inch, y, f"Status: {status.upper()}")
    
    # Summary
    y -= 0.5*inch
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, y, "Hiring Manager Summary")
    
    y -= 0.3*inch
    c.setFont("Helvetica", 10)
    
    # Wrap text
    summary_lines = []
    words = summary.split()
    line = ""
    for word in words:
        test_line = line + " " + word if line else word
        if c.stringWidth(test_line, "Helvetica", 10) < (width - 2*inch):
            line = test_line
        else:
            summary_lines.append(line)
            line = word
    if line:
        summary_lines.append(line)
    
    for line in summary_lines:
        c.drawString(1*inch, y, line)
        y -= 0.2*inch
    
    # Answers
    y -= 0.3*inch
    if y < 2*inch:  # New page if needed
        c.showPage()
        y = height - 1*inch
    
    c.setFont("Helvetica-Bold", 14)
    c.drawString(1*inch, y, "Interview Responses")
    
    y -= 0.3*inch
    c.setFont("Helvetica", 9)
    
    for question, answer in answers.items():
        if y < 1.5*inch:  # New page if needed
            c.showPage()
            y = height - 1*inch
        
        # Question
        c.setFont("Helvetica-Bold", 9)
        c.drawString(1*inch, y, f"Q: {question[:80]}...")  # Truncate long questions
        y -= 0.2*inch
        
        # Answer
        c.setFont("Helvetica", 9)
        c.drawString(1.2*inch, y, f"A: {answer[:80]}...")  # Truncate long answers
        y -= 0.4*inch
    
    # Footer
    c.setFont("Helvetica", 8)
    c.drawString(1*inch, 0.5*inch, "Confidential - For Internal Use Only")
    
    c.save()
    buffer.seek(0)
    return buffer


# ================================Fetch jobs and generate configs dynamically=====================================

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, model_kwargs={"response_format": {"type": "json_object"}})

# XANO Configuration
XANO_BASE_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:L-QNLSmb"

# In-memory cache for generated job configs
JOB_CONFIGS = {}


def fetch_job_from_xano(job_id: str) -> dict:
    """
    Fetch job details from XANO by job_id   
    Returns:
        dict: Job data from XANO
    """
    
    try:
        url = f"{XANO_BASE_URL}/job/{job_id}"
        response = requests.get(url)
        
        if response.status_code == 200:
            job_data = response.json()
            print(f"Successfully fetched job: {job_data.get('job_title', 'Unknown')}")
            return job_data
        else:
            print(f"Failed to fetch job: {response.status_code} - {response.text}")
            return None
            
    except Exception as e:
        print(f"Error fetching job from XANO: {e}")
        return None


def generate_job_config_from_description(job_description: str, job_title: str) -> dict:
    """
    Generate knockout questions, screening questions, and scoring model using LLM
    Returns:
        dict: Generated config with knockout_questions, questions, scoring_model
    """
    
    prompt = GENERATE_JOB_CONFIG_PROMPT.format(
        job_title=job_title,
        job_description=job_description
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        config = json.loads(response.content)
        
        print(f"Generated config for job: {job_title}")
        print(f"   - {len(config.get('knockout_questions', []))} knockout questions")
        print(f"   - {len(config.get('questions', []))} screening questions")
        print(f"   - {len(config.get('scoring_model', {}))} scoring rules")
        
        return config
        
    except json.JSONDecodeError as e:
        print(f"Failed to parse LLM response as JSON: {e}")
        print(f"Response was: {response.content}")
        return get_fallback_config()
    except Exception as e:
        print(f"Error generating config: {e}")
        return get_fallback_config()


def get_fallback_config() -> dict:
    """
    Fallback configuration if LLM generation fails
    """
    return {
        "knockout_questions": [
            "To work here, you must be legally eligible to work in the U.S. Can you confirm that you are?",
            "Next, You must be at least 18 years old for this role. Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?",
            "Do you have reliable transportation to and from our store located at {address}?"
        ],
        "questions": [
            "How many years of relevant work experience do you have?",
            "What interests you about this position?",
            "Are you comfortable working in a fast-paced environment?"
        ],
        "scoring_model": {
            "How many years of relevant work experience do you have?": {"rule": "Score = years * 3"},
            "What interests you about this position?": {"rule": "Detailed answer -> 5, Brief -> 2"},
            "Are you comfortable working in a fast-paced environment?": {"rule": "Yes -> 5, No -> 0"}
        }
    }


def get_or_generate_job_config(job_id: str) -> dict:
    """
    Get job config from cache or generate new one from XANO  
    Returns:
        dict: Job configuration with knockout_questions, questions, scoring_model
    """
    
    # Check cache first
    if job_id in JOB_CONFIGS:
        print(f"Using cached config for job_id: {job_id}")
        return JOB_CONFIGS[job_id]
    
    # Fetch job from XANO
    job_data = fetch_job_from_xano(job_id)
    
    if not job_data:
        print(f"Could not fetch job, using fallback config")
        return get_fallback_config()
    
    # Extract relevant fields
    job_title = job_data.get("job_title", "Unknown Position")
    job_description = job_data.get("description", "")
    
    # If no description
    if not job_description:
        print(f"job_description issue, using fallback config")
        return get_fallback_config()
    
    # Generate config using LLM
    config = generate_job_config_from_description(job_description, job_title)
    
    # Cache the result
    JOB_CONFIGS[job_id] = config
    
    return config



# ==========================================================================================================
# Question prompt

def generate_questions_config(eligibility_criteria: str, screening_questions: str):
    """
    Uses LLM to convert Eligibility_Criteria and Screening_Questions text
    into a structured JSON format:
    {
        "questions": [...],
        "scoring_model": { ... }
    }
    """

    json_llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, model_kwargs={"response_format": {"type": "json_object"}})

    prompt = f"""
    You are an expert screening assistant.
    Convert the given Eligibility Criteria and Screening Questions into a JSON object 
    with exactly the following structure:
    
    {{
        "questions": [list of plain questions],
        "scoring_model": {{
            "exact question": {{"rule": "short rule", "score": number}},
            "exact question": {{"rule": "...", "score": number}},
            ...
        }}
    }}
    
    Do NOT include any explanations or extra text — return **only valid JSON**.
    
    --- Eligibility Criteria ---
    {eligibility_criteria}
    
    --- Screening Questions ---
    {screening_questions}
    """

    response = json_llm.invoke([HumanMessage(content=prompt)])

    print(response.content)
    
    # Try parsing LLM response into JSON
    try:
        data = json.loads(response.content)
        print("Successfully parsed questions config JSON.")
    except json.JSONDecodeError:
        print("Could not parse response as JSON. Raw response:")
        print(response.content)
        return None

    return data



def get_job_details_by_id(job_id):
    
    XANO_API_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:L-QNLSmb/get_all_job_"
    response = requests.get(f"{XANO_API_URL}")

    if response.status_code == 200:
        
        jobs_data = response.json()
        print("Successfully Fetched jobs data:")
        
        for job in jobs_data:
            if job.get("id") == job_id:
                print("Successfully found Job")
                eligibility_criteria = job.get("Eligibility_Criteria")
                screening_questions = job.get("Screening_Questions")
        
        questions_config = generate_questions_config(eligibility_criteria, screening_questions)
        return questions_config     
    else:
        return None