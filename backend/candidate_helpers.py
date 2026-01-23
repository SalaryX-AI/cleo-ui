import json
from datetime import datetime
from langchain_openai import ChatOpenAI
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.5)

from prompts1 import JSON_REPORT_PROMPT


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



def extract_age_from_text(text: str) -> str:
    """
    Extract age from natural language using LLM
    
    Returns:
        - "18+" if user confirms being 18 or older
        - Integer age as string if specific age mentioned
        - "NONE" if age cannot be determined
    """
    
    print(f"extracting_age_from_text called...")
    prompt = f"""Extract the age from this text response. Follow these rules:

        1. If the person confirms they are 18 or older with affirmative words (yes, yeah, sure, yep, of course, definitely, absolutely), return exactly: 18+
        2. If the person mentions a specific age in numbers (e.g., "I am 33", "33 years old"), return only the number: 33
        3. If the person mentions age in words (e.g., "thirty-three", "twenty five"), convert to number: 33
        4. If the response is negative (no, nope, not yet), return: NONE
        5. If no clear age can be determined, return: NONE

        Return ONLY the extracted age - no extra text, no explanations, no punctuation.

        Examples:
        "yes I am" -> 18+
        "yes I am 20 years old" -> 20
        "I'm 25" -> 25
        "twenty-five years old" -> 25
        "no" -> NONE

        Text: "{text}"

        Age:"""
    
    response = llm.invoke(prompt)
    age = response.content.strip()
    
    # Clean up response - remove quotes, extra spaces
    age = age.replace('"', '').replace("'", "").replace('+', '').strip()
    
    # Validate response
    if age.upper() == "NONE" or age == "":
        return "NONE"
    
    # Check if it's the 18+ case
    if age == "18":
        return "18+"
    
    # Check if it's a valid integer
    try:
        age_int = int(age)
        if age_int > 0 and age_int < 120:  # Valid age range
            return str(age_int)
        else:
            return "NONE"
    except ValueError:
        # Not a number, could be "NONE" or malformed
        return "NONE"
    


def generate_json_report(data: dict) -> str:
    """Generate JSON report from data using LLM"""

    prompt = JSON_REPORT_PROMPT.format(
        name = data["name"],
        email = data["email"],
        phone = data["phone"],
        session_id = data["session_id"],
        knockout_answers = data["knockout_answers"],
        answers = data["answers"],
        score = data["score"],
        total_score = data["total_score"],
        current_time = datetime.now().isoformat()
    )
    
    print("Generating JSON report...")
    response = llm.invoke(prompt)
    
    # Parse JSON response
    try:
        # Clean response (remove markdown if present)
        json_text = response.content.strip()
        
        if json_text.startswith("```json"):
            json_text = json_text.replace("```json", "").replace("```", "").strip()
        elif json_text.startswith("```"):
            json_text = json_text.replace("```", "").strip()
        
        json_report = json.loads(json_text)
        
        print("Successfully generated JSON report....") 
        print(json.dumps(json_report, indent=2))

        return json_report
         
        
    except json.JSONDecodeError as e: 
        print(f"Failed to parse JSON report: {e}") 
        print(f"Response was: {response.content[:500]}") 
         
        # Fallback: Create basic JSON structure 
        json_report = create_fallback_report( 
            data["name"],  
            data["email"],  
            data["phone"],
            data["session_id"],
            data["knockout_answers"],
            data["answers"],
            data["score"],
            data["total_score"]
        ) 
        
    return json_report


def create_fallback_report(name, email, phone, session_id, knockout_answers, answers, score, total_score):
    """
    Create a fallback JSON report if LLM generation fails
    """
    from datetime import datetime
    
    
    return {
        "report_metadata": {
            "session_id": session_id,
            "generated_at": datetime.now().isoformat(),
            "report_version": "1.0"
        },
        "applicant_information": {
            "full_name": name,
            "email": email,
            "phone_number": phone,
            "address": None
        },
        "qualification": {
            "requirements": [
                {
                    "criterion": q,
                    "met": True,  
                    "evidence": a,
                    "importance": "High"
                }
                for q, a in knockout_answers.items()
            ],
            "overall_qualified": True
        },
        "experiences": [
            {
                "years_experience": 0,
                "job_title": None,
                "employer": None,
                "duration": None,
                "skills": None,
                "relevant_experience": "See screening answers for details"
            }
        ],
        "education": [],
        "fit_score": {
            "score": int(score),
            "qualification_score": 100,
            "experience_score": 70,
            "personality_score": 80,
            "rating": "Good" if score >= 60 else "Fair",
            "explanation": f"Candidate scored {score:.1f} out of {total_score:.1f} based on their responses."
        },
        "summary": {
            "eligibility_status": "Eligible" if score > 50 else "Not Eligible",
            "recommendation": "Recommend for interview" if score > 50 else "Do not recommend",
            "key_strengths": ["Completed screening process"],
            "concerns": [] if score > 50 else ["Score below threshold"]
        },
        "interview_notes": {
            "notable_responses": [f"{q}: {a}" for q, a in list(answers.items())[:2]],
            "overall_impression": "Candidate completed the screening process."
        }
    }