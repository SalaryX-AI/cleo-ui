"""Prompt templates for Cleo chatbot"""

from langchain.prompts import PromptTemplate


SYSTEM_PROMPT = """
    You are Cleo, a real person (not a robot) helping someone apply for a job through conversation.
    
    CRITICAL: Vary your wording naturally. Never use the same phrasing twice. Be creative and conversational like a real human would be not following a script.
    
    Style guidelines:
    - Use contractions (I'm, what's, that's, you're)
    - Vary your sentence structure
    - Be authentic and natural

    Remember: You're a helpful human named Cleo, not a chatbot. Respond like you would in a real conversation and use simple and clear language.
"""

# Greeting prompt
GREETING_PROMPT = PromptTemplate(
    input_variables=[],
    template="""
    Start by greeting the candidate warmly and politely and introduce yourself briefly (I am cleo).

    Keep your tone friendly, professional, and easy to understand.
    Use simple language.
    Example: Hello. I'm Cleo, the hiring assistant for Big Chicken. Thank you for your interest in this role.

    Your response (Maximum 20 words).
    """
)

CONSENT_EVALUATION_PROMPT = PromptTemplate(
    input_variables=["user_response"],
    template="""
    Question: Hi there! I'm Cleo. I'll ask a few quick questions for your screening. Are you ready to start?
    The candidate response: "{user_response}"
    
    Question: Are they willing to proceed with screening?
    
    Consider:
    - Positive intent (agreement, willingness, readiness) = Yes
    - Negative intent (refusal, postponement, disinterest) = No
    - Neutral/unclear intent (confusion, questions, vague) = Yes
    
    Think: What is their underlying intent?
    
    CRITICAL: Return ONLY one word - either Yes or No. Nothing else.
    """
)


# KNOCKOUT_QUESTION asking prompt
ASK_KNOCKOUT_QUESTION_PROMPT = PromptTemplate(
    input_variables=["question", "previous_question", "previous_answer"],
    template="""

    Question to ask: {question}
    Previous question: {previous_question}
    Previous answer: {previous_answer}

    Behavior rules:
    - If there is a previous question and answer, briefly acknowledge their response before asking this new question.
    - If there is no previous question (i.e., this is the first knockout question), skip the acknowledgment and start naturally."

    Style: Natural, conversational, brief. Don't greet - conversation already started.
    - Avoid words like "Hey" or "Oops".
    
    Return only the final text you would say to the candidate (Maximum 20 words).
    """
    )

# Knockout questions evaluation prompt
KNOCKOUT_EVALUATION_PROMPT = PromptTemplate(
    input_variables=["knockout_questions", "knockout_answers"],
    template="""
    Task: Evaluate if the candidate passed all knockout screening questions.
    
    Knockout Questions and Answers:
    {knockout_questions}
    {knockout_answers}
    
    Evaluation Rules:
    - These are CRITICAL eligibility questions
    - For legal authorization, transportation, availability questions:
      * "yes", "authorized", "have", "available", "can", "sure", "definitely", "Y" → PASS
      * "no", "not authorized", "don't have", "unavailable", "cannot", "Nope" → FAIL
    
    - For age questions (18 or older):
      * "yes", "I'm", "I am", any number ≥18, "old enough", "adult", "Y" → PASS
      * "no", "not", any number <18, "minor", "under 18", "Nope" → FAIL
      * Incomplete answers like "I'm", "yes I", "I am", "Y" → PASS (assume positive intent)
    
    - Be reasonably lenient: minor typos or incomplete responses that show positive intent → PASS
    - Be strict only on clear negatives: explicit "no" or disqualifying information → FAIL
    
    Examples:
    Q: "Are you legally authorized to work in the U.S.?" A: "no" → FAIL
    Q: "Are you 18 or older?" A: "I'm" → PASS (incomplete but positive intent)
    Q: "Are you 18 or older?" A: "yes I am" → PASS
    Q: "Are you 18 or older?" A: "Y" → PASS
    Q: "Are you 18 or older?" A: "I'm 17" → FAIL
    Q: "Do you have reliable transportation?" A: "no" → FAIL
    Q: "All questions answered positively" → PASS
    
    CRITICAL: Return ONLY one word - either "PASS" or "FAIL". Nothing else.
    
    Decision:
    """
)

# ==========================================================================================================


# Prompt for FIRST time asking (no validation failure)
PERSONAL_DETAIL_ASK_PROMPT = PromptTemplate(
    input_variables=["detail_type", "previous_question", "previous_answer"],
    template="""
    Task: Ask for the candidate's {detail_type} directly in a Professional way.

    Context:
    - Previous question: {previous_question}
    - Previous answer: {previous_answer}
    
    Instructions:
    - If previous_answer is "None": Ask for {detail_type} directly in a Professional way.
    - If previous_answer is NOT "None": Briefly acknowledge their answer ({previous_answer}) based on question ({previous_question}), then ask for {detail_type} directly.

    Style: Natural, conversational, brief. Don't greet - conversation already started.

    Return only the final text you would say to the candidate. (Maximum 20 words)
    """
)

# Prompt for VALIDATION FAILURE (re-asking)
PERSONAL_DETAIL_REASK_PROMPT = PromptTemplate(
    input_variables=["detail_type", "invalid_attempt"],
    template="""
    Task: The candidate provided an invalid {detail_type}: "{invalid_attempt}"

    Instructions:
    - Gently point out the issue with their "{invalid_attempt}" directly.
    - If the detail_type is phone number, remind them to include the country code (e.g., +1, +92).
    - Politely ask them to provide their {detail_type} again.
    - Avoid words like "Hey" or "Oops".

    Style: Natural, conversational, brief.

    Return only the final text you would say to the candidate. (Maximum 20 words)
    """
)


# Prompt for THIRD TIME VALIDATION FAILURE (re-asking with example)
PERSONAL_DETAIL_REASK_WITH_EXAMPLE_PROMPT = PromptTemplate(
    input_variables=["detail_type", "invalid_attempt", "example"],
    template="""
    Task: The candidate provided an invalid {detail_type}: "{invalid_attempt}"
    
    This is their third attempt, so let's help them with a clear example.

    Instructions:
    - Gently acknowledge they've had trouble with the format
    - If the detail_type is phone number, remind them to include the country code (e.g., +1, +92).
    - Show them a clear example: {example}
    - Politely ask them to try again using the example format
    - Be patient, encouraging, and helpful

    Style: Natural, supportive, understanding. Keep it brief but clear.

    Return only the final text you would say to the candidate (Maximum 25 words).
    """
)

# Question asking prompt
ASK_QUESTION_PROMPT = PromptTemplate(
    input_variables=["question", "previous_question", "previous_answer"],
    template="""
    
    Current question to ask: {question}
    Previous question: {previous_question}
    Previous answer: {previous_answer}

    Instructions:
    - If previous_answer is "None": Just ask for {question} directly in a Professional way
    - If previous_answer is NOT "None": Briefly acknowledge their answer ({previous_answer}) based on question ({previous_question}), then ask for {question} directly.
    - Avoid words like "Hey", "Oops", "Thanks".

    Style: Natural, conversational, brief. Don't greet - conversation already started.
    
    Return only the final text you would say to the candidate (Maximum 20 words).
    """
)


# ==========================================================================================================
# Scoring prompt
SCORING_PROMPT = PromptTemplate(
    input_variables=["answers", "scoring_model"],
    template="""
    Calculate the score for each question based on the answers and scoring rules provided.

    Candidate Answers:
    {answers}

    Scoring Rules:
    {scoring_model}

    INSTRUCTIONS:
      1. Extract numbers from text answers:
        - "6 years" -> 6
        - "twenty years" -> 20
        - "yes" or "no" -> boolean

      2. Apply formulas EXACTLY:
        - "Score = years * 5" with "6 years" -> 6 * 5 = 30
        - "Score = min(years, 5) * 5" with "6 years" -> min(6, 5) * 5 = 5 * 5 = 25
        - "Score = months / 2" with "12 months" -> 12 / 2 = 6

      3. For Yes/No rules:
        - "Yes -> 10, No -> 0" with "yes" -> 10
        - "Yes -> 10, No -> 0" with "no" -> 0

    Return ONLY a JSON object in this exact format:
    {{
        "scores": {{"question1": score1, "question2": score2, ...}},
        "score": total_sum,
        "total_score": 20
    }}

    CRITICAL: Apply min(), max(), and other functions correctly in formulas!
    Be precise with numbers and ensure score is the sum of all individual scores."""
)

# Summary prompt
SUMMARY_PROMPT = PromptTemplate(
    input_variables=["name", "answers", "score", "total_score"],
    template="""
    Generate a professional summary report for the hiring manager about candidate {name}.
    
    Candidate's responses:
    {answers}
    
    Score: {score} out of {total_score} ({score}/{total_score}*100)%
    
    Create a concise employer-focused summary that includes:
    1. Overall impression of the candidate
    2. Key strengths based on their answers
    3. Any areas of concern or gaps
    4. Hiring recommendation:
       - Score above 70%: "Strong candidate - Recommend for interview"
       - Score 50-70%: "Qualified candidate - Consider for interview"
       - Score below 50%: "Does not meet minimum requirements at this time"
    
    Keep it professional and objective. 5 sentences maximum.
    Format as plain text, no special characters or markdown."""
)


# End conversation prompt
END_PROMPT = PromptTemplate(
    input_variables=["name"],
    template="""
    Use a friendly, professional tone.

    Return only the final message
    Example: Great Job! You've successfully completed the initial application. Your information has been securely saved and submitted.
    """
)


GENERATE_JOB_CONFIG_PROMPT = PromptTemplate(
    input_variables=["job_title", "job_description", "job_location"],
    template="""    
    
    You are an expert HR assistant. Based on the job description below, generate a screening configuration.

    Job Title: {job_title}
    Job Description: {job_description}
    Job Location: {job_location}

    Generate a JSON object with the following structure:
    {{
        "knockout_questions": [
            "4 knockout questions that check basic eligibility (age 18+, work authorization, availability, transportation)"
        ],
        "questions": [
            "3-5 screening questions specific to this role that assess relevant skills and experience"
        ],
        "scoring_model": {{
            "exact question text": {{"rule": "scoring rule like 'Score = years * 5' or 'Yes -> 10, No -> 2'"}},
            ...
        }}
    }}

    IMPORTANT RULES:
    1. Knockout questions MUST include:
    - Legal work authorization in U.S.
    - Age 18+ requirement
    - Schedule availability (evening/weekend shifts)
    - Transportation to store at {job_location} (use this exact placeholder)

    2. Screening questions should be:
    - Specific to the role (e.g., "How many years of X experience?")
    - Measurable (experience in years/months, yes/no questions)
    - Relevant to job requirements

    3. Scoring model rules:
    - For experience: "Score = years * multiplier" or "Score = months / divisor"
    - For yes/no: "Yes -> high_score, No -> low_score"
    - Total should sum to approximately 20-30 points max
    - Be consistent with question text (copy exact question)

    4. Return ONLY valid JSON, no markdown, no explanations.

    Generate the configuration now:"""
    )


JSON_REPORT_PROMPT = PromptTemplate(
    input_variables=["name", "email", "phone", "session_id", "knockout_answers", "answers", "score", "total_score", "work_experience", "education", "address", "current_time"],
    template="""
    You are an expert HR analyst. Generate a comprehensive JSON report for the hiring manager based on the candidate's screening interview.

    CANDIDATE INFORMATION:
    - Name: {name}
    - Email: {email}
    - Phone: {phone}
    - Session ID: {session_id}

    KNOCKOUT QUESTIONS (Eligibility Criteria):
    {knockout_answers}

    SCREENING QUESTIONS (Skills & Experience):
    {answers}

    WORK EXPERIENCE:
    {work_experience}

    EDUCATION:
    {education}

    SCORES:
    - Total Score: {score} out of {total_score}
    - Percentage: {score}/{total_score} * 100

    Generate a JSON report with the following exact structure:

    {{
      "report_metadata": {{
        "session_id": "{session_id}",
        "generated_at": "{current_time}",
        "report_version": "1.0"
      }},
      "applicant_information": {{
        "full_name": "{name}",
        "email": "{email}",
        "phone_number": "{phone}",
        "address": {address}
      }},
      "qualification": {{
        "requirements": [
          {{
            "criterion": "Criterion name from knockout questions",
            "met": true/false based on answer,
            "evidence": "Quote from candidate's answer",
            "importance": "High/Medium/Low"
          }}
          // One object for each knockout question
        ],
        "overall_qualified": true/false (true if all High importance criteria met)
      }},
      "experiences": [
        {{
          "years_experience": Calculate total_experience (years and months) from duration,
          "job_title": null (if not mentioned),
          "employer": null (if not mentioned),
          "duration": null (if not mentioned) format should be (start date - end date),
          "skills": any 2-3 skills based on relevant_experience,
          "relevant_experience": "Summary of candidate's experience from their answers (2-3 sentences)"
        }}
      ],
      "education": {education},
      "fit_score": {{
        "total_score": {score} as integer,
        "qualification_score": 0-100 based on knockout answers,
        "experience_score": 0-100 based on screening answers,
        "personality_score": 0-100 based on communication quality,
        "rating": "Excellent" if >80, "Good" if 60-80, "Fair" if 40-60, "Poor" if <40,
        "explanation": "explanation of the scores (2-3 sentences)"
      }},
      "summary": {{
        "eligibility_status": "Eligible" or "Not Eligible",
        "recommendation": "Strongly recommend/Recommend/Consider/Do not recommend + position type",
        "key_strengths": [
          "List 3-5 key strengths from answers"
        ],
        "concerns": [
          "List any concerns or gaps, or empty array if none"
        ]
      }},
      "interview_notes": {{
        "notable_responses": [
          "2-3 notable quotes or responses from candidate"
        ],
        "overall_impression": "overall impression (2-3 sentences)"
      }}
    }}

    IMPORTANT:
    1. Return ONLY valid JSON, no markdown, no code blocks, no explanations
    2. All text fields must be properly escaped for JSON
    3. Use actual data from the candidate's answers
    4. Be objective and professional
    5. Ensure all boolean values are lowercase (true/false not True/False)
    
    Generate the JSON report now:
    """
)