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
    Q: "Are you 18 or older?" A: "Y", "y" → PASS (incomplete but positive intent)
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

PHONE_ANALYSIS_PROMPT = """You are Cleo, a friendly AI hiring assistant collecting a phone number from a job applicant.

The applicant was asked: "What is your phone number?"
Their response: "{user_input}"

Analyze their response and return ONLY a JSON object in this exact format:
{{
    "intent": "provided" | "refusal" | "invalid",
    "phone": "extracted E.164 phone number or null",
    "message": "your conversational response message or null"
}}

Intent rules:
- "provided": they gave something that looks like a phone number (digits, formatted number, with or without country code)
- "refusal": they explicitly declined, said no, don't want to share, skip, or expressed unwillingness
- "invalid": gibberish, random letters, a name, unrelated text — not a refusal but not a number either

Phone rules (only when intent is "provided"):
- Normalize to E.164 format
- If no country code and starts with 0 → assume Pakistan, use +92
- If no country code and starts with 92 or 1 → add + prefix
- If no country code and neither → assume US, add +1
- Return null for refusal or invalid

Message rules:
- "provided": return null (no message needed, number will be validated separately)
- "refusal" attempt 1: warm message acknowledging their concern, gently explaining the number is needed for identity verification and interview reminders, ask again naturally
- "refusal" attempt 2+: polite hard stop — explain the number is required to proceed, thank them for their time
- "invalid": acknowledge what they said, explain you need a valid phone number, give a natural example like +1 555 123 4567

Examples:
User: "no" → {{"intent": "refusal", "phone": null, "message": "I completely understand if you're hesitant! Your number is only used to verify your identity and send interview updates. Could you share it so we can keep things moving (e.g. +1 555 123 4567)"}}
User: "+1 555 123 4567" → {{"intent": "provided", "phone": "+15551234567", "message": null}}
User: "mbmbmb" → {{"intent": "invalid", "phone": null, "message": "That doesn't look like a phone number — could you share your number including the country code? For example: +1 555 123 4567"}}
User: "I don't want to give my number" → {{"intent": "refusal", "phone": null, "message": "..."}}
User: "03001234567" → {{"intent": "provided", "phone": "+923001234567", "message": null}}

Refusal attempt count: {attempt_count}

Return ONLY the JSON. No explanation, no markdown."""

# Prompt for VALIDATION FAILURE (re-asking)
PERSONAL_DETAIL_REASK_PROMPT = PromptTemplate(
    input_variables=["detail_type", "invalid_attempt"],
    template="""
    Task: A candidate was asked for their {detail_type} but responded with: "{invalid_attempt}"

    Instructions:
    - Analyze what they said and acknowledge it naturally based on what it looks like:
        - If it looks like random characters or a typo, gently point that out.
        - If it's a greeting or off-topic response, briefly acknowledge it.
        - If it's a partial answer (e.g. only first name when full name is needed), acknowledge what they gave and ask for the rest.
        - If it's a real value but in the wrong format, point out the issue specifically.
    - If the detail_type is phone number, remind them to include the country code (e.g., +1, +92).
    - Always end by asking them to provide their {detail_type} again.
    - Avoid words like "Hey" or "Oops".

    Style: Natural, conversational, brief.

    Return only the final text you would say to the candidate. (Maximum 25 words)
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
    - If previous_answer is NOT "None": Briefly acknowledge their answer ({previous_answer}) based on question ({previous_question}), then ask for {question} directly Don't change the question's text and sequence.
    - Avoid words like "Hey", "Oops", "Thanks".

    Style: Natural, conversational, brief. Don't greet - conversation already started.
    
    Return only the final text you would say to the candidate (Maximum 20 words).
    """
)


# ==========================================================================================================
SCORING_PROMPT = PromptTemplate(
    input_variables=["answers", "scoring_model", "total_score"],
    template="""
You are a hiring evaluator. Score each candidate answer against the provided scoring rules.

Candidate Answers:
{answers}

Scoring Rules:
{scoring_model}

SCORING INSTRUCTIONS:

1. YES / NO RULES
   Match semantically — do not require exact words.
   - "Yes -> 5, No -> 0": "Absolutely", "Of course", "Yep" → 5 | "No", "I can't", "Not really" → 0

2. TIERED RULES
   Use semantic judgment to pick the closest tier.
   - "Yes -> 4, Partial -> 2, No -> 0":
       "Fully available" → 4 | "Available most weekends" → 2 | "Not available" → 0
   - "Yes -> 3, Somewhat -> 2, No -> 0":
       "Very experienced" → 3 | "Some experience" → 2 | "None" → 0
   - "Yes -> 3, Willing to learn -> 2, No -> 0":
       "I know this well" → 3 | "Happy to learn" → 2 | "Not interested" → 0

3. EXPERIENCE / YEARS RULES
   - "2+ years -> 5, 1-2 years -> 4, 6 months to 1 year -> 2, Less than 6 months -> 1, 0 years -> 0":
       "2.5 years" → 5 | "1.3 years" → 4 | "8 months" → 2 | "3 months" → 1 | "0 years" → 0

4. CERTIFICATION RULES
   - "ServSafe/TIPS/Food Safety cert present -> 2, Other cert -> 1, None -> 0":
       "I have ServSafe" → 2 | "I have CPR" → 1 | "No certifications" → 0

5. COMPLIANCE / CONSENT RULES
   - "Yes -> 5, No -> 0": Treat any clear agreement as Yes → 5, any refusal as No → 0

6. MISSING OR UNANSWERED
   If a question key exists in scoring rules but has no matching answer, assign 0.

7. WEIGHT FIELD
   The "weight" field is for reference only — do NOT multiply by it.
   The rule already expresses the final point value directly.

8. BACKGROUND CHECK
   The key "background_check_consent" maps to the candidate's response to the Level II background check question.

Return ONLY a valid JSON object — no markdown, no explanation, no extra text:
{{
    "scores": {{"<scoring_rule_key>": <score>, ...}},
    "score": <sum of all scores>,
    "total_score": {total_score}
}}

CRITICAL RULES:
- Every key in scoring_model MUST have a corresponding entry in "scores", even if score is 0.
- "score" MUST equal the exact arithmetic sum of all values in "scores".
- "total_score" is always {total_score}.
- Return ONLY the JSON object."""
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