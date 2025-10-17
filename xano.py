import requests
from langchain_openai import ChatOpenAI
from langchain.schema import HumanMessage
import json

def generate_questions_config(eligibility_criteria: str, screening_questions: str):
    """
    Uses LLM to convert Eligibility_Criteria and Screening_Questions text
    into a structured JSON format:
    {
        "questions": [...],
        "scoring_model": { ... }
    }
    """

    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3)

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

    response = llm.invoke([HumanMessage(content=prompt)])

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