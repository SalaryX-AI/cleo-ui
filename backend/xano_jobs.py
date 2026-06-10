import requests
import json
import asyncio
import sys
from psycopg import AsyncConnection
from psycopg.rows import dict_row
from dotenv import load_dotenv
import os

from xano import get_fallback_config
from prompts1 import GENERATE_JOB_CONFIG_PROMPT
from langchain.schema import HumanMessage
from langchain_openai import ChatOpenAI

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.3, model_kwargs={"response_format": {"type": "json_object"}})

def parse_job_specific_qualifiers(items: list) -> dict:
    """
    Parse JOB-SPECIFIC QUALIFIERS section from Xano API response.
    Sorts by order field. Identifies required (hard stop) vs flagged (soft) questions.
    """

    def clean_msg(text: str) -> str:
        if not text:
            return ""
        if text.strip().lower() in ("continue", "n/a", "-", ""):
            return ""
        return text.strip()

    # Sort by order
    items.sort(key=lambda x: x.get("order", 999))

    questions                 = []
    required_questions        = {}
    flagged_questions         = {}
    question_acknowledgements = {}
    scoring_model             = {}

    for item in items:
        q_text      = item.get("question_text", "").strip()
        proceed     = clean_msg(item.get("Proceed_ahead", ""))
        no_proc     = clean_msg(item.get("do_not_proceed", ""))
        is_required = item.get("isRequired", False)
        flag_mgr    = item.get("flag_for_manager", False)
        flag_reason = item.get("flag_reason", "")
        weight      = item.get("scoring_weight", 0)
        rule        = item.get("scoring_rule", "")
        no_resp_msg = clean_msg(item.get("no_response_message", ""))

        if not q_text:
            continue

        # Add to ordered questions list
        questions.append(q_text)

        # Acknowledgement on YES
        question_acknowledgements[q_text] = proceed

        # ── Required (hard stop on NO) ────────────────────────────────────────
        if is_required and not flag_mgr:
            required_questions[q_text] = {
                "pass_ack":     proceed,
                "fail_message": no_proc,
            }

        # ── Flagged (soft — show message + flag manager on NO) ────────────────
        elif flag_mgr:
            flagged_questions[q_text] = {
                "pass_ack":    proceed,
                "flag_reason": flag_reason,
                "no_response": no_proc,   # do_not_proceed = message shown before continuing
            }

        # ── Scoring model entry ───────────────────────────────────────────────
        if weight:
            scoring_model[q_text] = {
                "rule":     rule,
                "weight":   weight,
                "category": "Skills"
            }

    return {
        "questions":                  questions,
        "required_questions":         required_questions,
        "flagged_questions":          flagged_questions,
        "question_acknowledgements":  question_acknowledgements,
        "scoring_model":              scoring_model,
    }


async def fetch_job_specific_qualifiers(template_id: str) -> dict:
    """Fetch JOB-SPECIFIC QUALIFIERS questions from Xano for a given template"""
    try:
        url = f"https://xoho-w3ng-km3o.n7e.xano.io/api:hesLDkGa/questions?template_id={template_id}"
        response = requests.get(url)
        
        response.raise_for_status()
        
        items = response.json()
        print(f"[XANO] Fetched {len(items)} job-specific qualifier questions")
        return parse_job_specific_qualifiers(items)
    except Exception as e:
        print(f"[XANO] Error fetching job-specific qualifiers: {e}")
        return {
            "questions":                  [],
            "required_questions":         {},
            "flagged_questions":          {},
            "question_acknowledgements":  {},
            "scoring_model":              {},
        }

def parse_template(items: list) -> dict:
    """
    Convert Xano API response into internal job config format.
    Sections: GREETING, ELIGIBILITY, JOB-SPECIFIC QUALIFIERS,
              WORK HISTORY & EDUCATION, BACKGROUND CHECK DISCLOSURE, FINAL WRAP-UP
    """

    def clean_msg(text: str) -> str:
        """Return empty string if message is a no-op like 'continue'"""
        if not text:
            return ""
        if text.strip().lower() in ("continue", "n/a", "-", ""):
            return ""
        return text.strip()

    # ── Sort by order first, then created_at as tiebreaker ───────────────────
    items.sort(key=lambda x: (x.get("order", 999), x.get("created_at", 0)))

    greeting_bubbles          = []
    greeting_ready_question   = {}
    knockout_questions        = []
    kq_pass_acks              = {}
    kq_fail_messages          = {}
    kq_ambiguity_msgs         = {}
    questions                 = []
    required_questions        = {}
    flagged_questions         = {}
    question_acknowledgements = {}
    end_messages              = []
    scoring_model             = {}

    # WORK HISTORY & EDUCATION — identified by keyword matching
    certifications_question   = {}
    referral_question         = {}
    military_question         = {}

    for item in items:
        section     = item.get("Section", "").strip()
        q_text      = item.get("question_text", "").strip()
        q_type      = item.get("type", "").strip()
        proceed     = clean_msg(item.get("Proceed_ahead", ""))
        no_proc     = clean_msg(item.get("do_not_proceed", ""))
        is_required = item.get("isRequired", False)
        flag_mgr    = item.get("flag_for_manager", False)
        flag_reason = item.get("flag_reason", "")
        weight      = item.get("scoring_weight", 0)
        rule        = item.get("scoring_rule", "")
        ambiguity   = clean_msg(item.get("ambiguity_fail_message", ""))
        no_resp_msg = clean_msg(item.get("no_response_message", ""))

        # ── GREETING ─────────────────────────────────────────────────────────
        if section == "GREETING":
            if q_type == "Cleo Bubble":
                greeting_bubbles.append(q_text)
            elif q_type == "Yes / No":
                # "Ready to start?" question
                greeting_ready_question = {
                    "question":       q_text,
                    "do_not_proceed": no_proc or "No problem! Feel free to come back anytime.",
                }

        # ── ELIGIBILITY (knockout questions) ─────────────────────────────────
        elif section == "ELIGIBILITY":
            knockout_questions.append(q_text)
            kq_pass_acks[q_text]     = proceed
            kq_fail_messages[q_text] = no_proc
            # Use ambiguity_fail_message if set, fallback to do_not_proceed
            kq_ambiguity_msgs[q_text] = ambiguity or no_proc

            if weight:
                scoring_model[q_text] = {
                    "rule":     rule,
                    "weight":   weight,
                    "category": "Basic Requirements"
                }

        # ── JOB-SPECIFIC QUALIFIERS (screening questions) ────────────────────
        elif section == "JOB-SPECIFIC QUALIFIERS":
            questions.append(q_text)
            question_acknowledgements[q_text] = proceed

            if is_required and not flag_mgr:
                # Hard stop on NO
                required_questions[q_text] = {
                    "pass_ack":     proceed,
                    "fail_message": no_proc,
                }
            elif flag_mgr:
                # Soft flag on NO
                flagged_questions[q_text] = {
                    "pass_ack":    proceed,
                    "flag_reason": flag_reason,
                    "no_response": no_resp_msg,
                }

            if weight:
                scoring_model[q_text] = {
                    "rule":     rule,
                    "weight":   weight,
                    "category": "Skills"
                }

        # ── WORK HISTORY & EDUCATION ─────────────────────────────────────────
        elif section == "WORK HISTORY & EDUCATION":
            q_lower = q_text.lower()

            if "certif" in q_lower:
                certifications_question = {
                    "question":   q_text,
                    "proceed_ack": proceed,
                }
                if weight:
                    scoring_model["certifications"] = {
                        "rule": rule, "weight": weight, "category": "Certifications"
                    }

            elif "hear about" in q_lower or "referred" in q_lower:
                referral_question = {
                    "question":    q_text,
                    "proceed_ack": proceed,
                }

            elif "military" in q_lower:
                military_question = {
                    "question":    q_text,
                    "proceed_ack": proceed,
                }

        # ── BACKGROUND CHECK DISCLOSURE ───────────────────────────────────────
        elif section == "BACKGROUND CHECK DISCLOSURE":
            if weight:
                scoring_model["background_check_consent"] = {
                    "rule": rule, "weight": weight, "category": "Compliance"
                }

        # ── FINAL WRAP-UP (end bubbles) ───────────────────────────────────────
        elif section == "FINAL WRAP-UP":
            if q_type == "Cleo Bubble":
                end_messages.append(q_text)

    return {
        "greeting_messages":          greeting_bubbles,
        "greeting_ready_question":    greeting_ready_question,
        "knockout_questions":         knockout_questions,
        "kq_pass_acks":               kq_pass_acks,
        "kq_fail_messages":           kq_fail_messages,
        "kq_ambiguity_msgs":          kq_ambiguity_msgs,
        "questions":                  questions,
        "required_questions":         required_questions,
        "flagged_questions":          flagged_questions,
        "question_acknowledgements":  question_acknowledgements,
        "certifications_question":    certifications_question,
        "referral_question":          referral_question,
        "military_question":          military_question,
        "end_messages":               end_messages,
        "scoring_model":              scoring_model,
    }


async def save_job_config_to_db(job_id: str, config: dict):
    """Save job config to PostgreSQL database"""
    connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
    
    async with await AsyncConnection.connect(
        connection_string,
        autocommit=True,
        row_factory=dict_row
    ) as conn:
        # Create table if not exists
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS job_configs (
                job_id TEXT PRIMARY KEY,
                config JSONB NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Insert or update config
        await conn.execute("""
            INSERT INTO job_configs (job_id, config, updated_at)
            VALUES (%s, %s, CURRENT_TIMESTAMP)
            ON CONFLICT (job_id) 
            DO UPDATE SET config = EXCLUDED.config, updated_at = CURRENT_TIMESTAMP
        """, (job_id, json.dumps(config)))
        
        print(f"Saved job config for job_id: {job_id}")


async def read_job_config_from_db(job_id: str = None):
    """Read job config(s) from PostgreSQL database"""
    connection_string = os.getenv("POSTGRES_CONNECTION_STRING")
    
    async with await AsyncConnection.connect(
        connection_string,
        autocommit=True,
        row_factory=dict_row
    ) as conn:
        if job_id:
            # Read specific job config
            result = await conn.execute("""
                SELECT config FROM job_configs WHERE job_id = %s
            """, (job_id,))
            
            row = await result.fetchone()
            if row:
                return row['config']
            return None
        else:
            # Read all job configs
            result = await conn.execute("""
                SELECT job_id, config FROM job_configs
            """)
            
            configs = {}
            async for row in result:
                configs[row['job_id']] = row['config']
            
            return configs



def generate_job_config_from_description(job_description: str, job_title: str, job_location: str) -> dict:
    """
    Generate knockout questions, screening questions, and scoring model using LLM
    Returns:
        dict: Generated config with knockout_questions, questions, scoring_model
    """
    
    prompt = GENERATE_JOB_CONFIG_PROMPT.format(
        job_title=job_title,
        job_description=job_description,
        job_location=job_location
    )

    try:
        response = llm.invoke([HumanMessage(content=prompt)])
        config = json.loads(response.content)

        print("Generated config:", config)
        
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
    


async def get_all_jobs():    
    
    """Fetch all jobs from Xano, generate configs, and save to DB"""
    
    XANO_API_URL = "https://xoho-w3ng-km3o.n7e.xano.io/api:L-QNLSmb/All_Jobs"
    response = requests.get(f"{XANO_API_URL}")

    if response.status_code == 200:
        
        jobs_data = response.json()
        # print("Successfully Fetched jobs data: ", jobs_data)
        print("Successfully Fetched jobs data...")
        print(f"Total jobs fetched: {len(jobs_data)}")
        
        for job in jobs_data:
            
            job_id = job.get("id")
            job_title = job.get("job_title")
            job_description = job.get("job_description")
            job_location = job.get("job_location")

            config = generate_job_config_from_description(job_description, job_title, job_location)

           # Save to database
            await save_job_config_to_db(job_id, config)
        
        return config     
    
    else:
        return None


if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(get_all_jobs())
 
    # print("Read job config from DB:", asyncio.run(read_job_config_from_db()))
    # print("Read job config from DB:", asyncio.run(read_job_config_from_db("b44fbf2b-8f12-49c0-8e91-3b564f98e7c1")))