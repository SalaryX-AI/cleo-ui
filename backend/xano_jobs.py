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