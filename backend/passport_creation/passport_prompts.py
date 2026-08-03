"""Prompts and static messages for the Cleo Work Passport™ flow"""

from langchain.prompts import PromptTemplate


# ── Greeting bubbles (staggered) ─────────────────────────────────────────────

PASSPORT_GREETING_BUBBLE_1 = (
    "Hi, I’m Cleo — your work passport helper. "
    "Let’s turn your experience, skills, and availability into a ready-to-share "
    "Cleo Work Passport™ in just a few easy steps."
)

PASSPORT_GREETING_BUBBLE_2 = (
    "No more long forms for one job. I’ll gather your work history, skills, and availability in under "
    "5 minutes, then build a Candidate Passport you can share with many hiring managers right away."
)

PASSPORT_GREETING_BUBBLE_3 = (
    "Before we start, your privacy is our priority: Your Work Passport remains completely private. "
    "Nothing is shared with any employer unless you give explicit permission."
)

# ── Post-name acknowledgement ─────────────────────────────────────────────────

PASSPORT_POST_NAME_PROMPT = PromptTemplate(
    input_variables=["first_name"],
    template=(
        "Great to meet you, {first_name}! Let's make sure we have the basics covered first. "
        "Use the first name throughout to keep things personal and warm. "
        "Acknowledge their name naturally — maximum 12 words."
    )
)

# ── Shift preference ──────────────────────────────────────────────────────────

PASSPORT_ASK_SHIFT = (
    "Frontline environments run on all kinds of schedules. "
    "What shifts work best for your lifestyle? (Select all that apply 👇)"
)

PASSPORT_SHIFT_CONFIRMED = (
    "Perfect! Flexibility is a huge superpower for frontline teams. "
    "I've logged your shift preferences into your profile tracker. ✅"
)

PASSPORT_SHIFT_NONE_SELECTED = (
    "Please select at least one shift preference so we can match you with the right opportunities!"
)

# ── Address / location ────────────────────────────────────────────────────────

PASSPORT_ASK_LOCATION = (
    "Let's make sure we find opportunities close to home. "
    "What is your current city/state or ZIP code, "
)

PASSPORT_LOCATION_CONFIRMED_PROMPT = PromptTemplate(
    input_variables=["location"],
    template=(
        "The candidate provided this location/commute: \"{location}\"\n\n"
        "Respond warmly confirming you've mapped their location. "
        "Reference what they said naturally. Maximum 15 words."
    )
)

# ── Screening question acknowledgements (Q5–Q8) ───────────────────────────────

PASSPORT_SCREENING_ACK_PROMPT = PromptTemplate(
    input_variables=["question", "answer", "first_name"],
    template=(
        "You are Cleo, a warm career assistant building {first_name}'s Work Passport.\n\n"
        "Question asked: \"{question}\"\n"
        "Candidate answered: \"{answer}\"\n\n"
        "Acknowledge their answer enthusiastically and naturally — highlight a specific detail "
        "from what they said to show you were listening. Then transition smoothly to the next step.\n\n"
        "Rules:\n"
        "- Do NOT start with 'I'\n"
        "- Do NOT repeat the question back\n"
        "- Sound genuinely impressed where appropriate\n"
        "- Maximum 25 words"
    )
)

# ── Post-Q8 transition (before contact verification) ─────────────────────────

PASSPORT_PRE_CONTACT_MESSAGE = (
    "Awesome! I've got all those details down. 🎉\n\n"
    "While we were chatting, I mapped out your primary skills and experience. "
    "I'm packaging these directly into your Cleo Work Passport™ so you don't have to type them out again.\n\n"
    "Let's lock down your secure contact details next!"
)

# ── Work history ──────────────────────────────────────────────────────────────

PASSPORT_ASK_WORK_HISTORY = (
    "Verified! Now, let's quickly review your work history. "
    "Beyond what we've already discussed, what was your most recent job title and how long were you with that employer?"
)

# ── Military ─────────────────────────────────────────────────────────────────

PASSPORT_ASK_MILITARY = (
    "One optional question 💙 — Have you ever served in the U.S. military?"
)

PASSPORT_MILITARY_THANKS = (
    "Thank you for your service 🇺🇸 We'd love to note that in your Passport. "
    "Feel free to share your branch, duty, or rank — all optional."
)

# ── Wrap-up bubbles (W1–W4) ───────────────────────────────────────────────────

PASSPORT_WRAP_W1 = (
    "Phenomenal job! 🌟 Your identity has been authenticated, your parameters are structured, "
    "and your official Cleo Candidate Passport Account is now LIVE."
)

PASSPORT_WRAP_W2 = (
    "Here is the link to access your Candidate Passport: https://app.cleohr.com/auth\n\n"
    "You can tap it anytime to view your verified skills dashboard, or copy and text it directly to hiring managers to apply on the spot!"
)

PASSPORT_WRAP_W3 = (
    "Thank you for letting Cleo help build your career pathway. Goodbye and good luck! 🍀"
)

# ── Professional summary prompt ───────────────────────────────────────────────

PASSPORT_SUMMARY_PROMPT = PromptTemplate(
    input_variables=[
        "years_experience", "industries", "skills",
        "tools", "certifications", "work_ethic"
    ],
    template="""You are writing a professional summary paragraph for a candidate's Work Passport.

Write a single, punchy 2-3 sentence paragraph that combines:
- Years/level of experience: {years_experience}
- Primary industries/roles: {industries}
- Key skills and tools: {skills} | {tools}
- Certifications: {certifications}
- Standout trait or work ethic: {work_ethic}

Rules:
- Write in third person ("Versatile professional with...", "Experienced worker...")
- Be specific — use the actual skills, tools, and industries provided
- Sound confident and professional, not generic
- If any field is empty or null, skip it naturally — do NOT mention it is missing
- Maximum 3 sentences, under 80 words total
- Return ONLY the paragraph, no labels, no markdown

Example output:
"Versatile frontline professional with 3+ years of experience in warehouse operations and facility maintenance. Proficient with inventory scanners, hand/power tools, and commercial paint sprayers. Known for strong adaptability, reliability across varied shift schedules, and clean safety records."
"""
)


# ── Passport profile generation prompt ───────────────────────────────────────

PASSPORT_PROFILE_PROMPT = PromptTemplate(
    input_variables=[
        "name", "email", "phone", "session_id",
        "shift_preferences", "location", "commute_method",
        "knockout_answers", "screening_answers",
        "work_experience", "education", "military",
        "current_time"
    ],
    template="""
You are an expert HR analyst. Generate a comprehensive Candidate Passport JSON profile.

CANDIDATE INFORMATION:
- Name: {name}
- Email: {email}
- Phone: {phone}
- Session ID: {session_id}
- Location: {location}
- Preferred Commute: {commute_method}
- Shift Preferences: {shift_preferences}

ELIGIBILITY (Knockout Questions):
{knockout_answers}

BACKGROUND (Screening Questions):
{screening_answers}

WORK HISTORY:
{work_experience}

EDUCATION:
{education}

MILITARY SERVICE:
{military}

Generate a JSON passport profile with the following exact structure:

{{
  "passport_metadata": {{
    "session_id": "{session_id}",
    "generated_at": "{current_time}",
    "passport_version": "1.0",
    "status": "active"
  }},
  "personal_information": {{
    "full_name": "{name}",
    "email": "{email}",
    "phone_number": "{phone}",
    "location": "{location}",
    "commute_method": "{commute_method}",
    "shift_preferences": {shift_preferences}
  }},
  "eligibility": {{
    "work_authorized": true/false based on knockout answers,
    "age_verified": true/false based on knockout answers,
    "overall_eligible": true if both above are true
  }},
  "experience_profile": {{
    "primary_industries": ["List 2-3 industries from screening answers"],
    "years_experience": "Calculate or estimate from work history — null if not provided",
    "top_skills": ["List 4-6 specific skills mentioned by candidate"],
    "tools_and_equipment": ["List specific tools/equipment mentioned"],
    "certifications": [
              {{
                "certificate_name": "Name of certification mentioned",
                "expiry_date": null
              }}
            ],
    "physical_capability": true/false based on Q8 answer,
    "work_history": [
      {{
        "job_title": "title or null",
        "employer": "employer or null",
        "duration": "start - end or null",
        "relevant_experience": "2-3 sentence summary or null"
      }}
    ]
  }},
  "education": {{
    "highest_level": "education level or null if not provided",
    "note": "Education details not provided — if education is null or empty"
  }},
  "military_service": {{
    "served": true/false,
    "details": "branch/duty/rank or null if not provided or declined"
  }},
  "fit_score": {{
    "total_score": 0-100 integer,
    "breakdown": {{
      "eligibility_score": 0-100 based on knockout answers,
      "experience_score": 0-100 based on screening answers and work history,
      "versatility_score": 0-100 based on range of skills and industries,
      "availability_score": 0-100 based on shift flexibility
    }},
    "rating": "Excellent if >80, Good if 60-80, Fair if 40-60, Poor if <40",
    "explanation": "2-3 sentence explanation of the overall score"
  }},
  "passport_summary": {{
    "headline": "One powerful sentence summarizing the candidate's profile",
    "key_strengths": ["List 3-5 key strengths"],
    "best_fit_roles": ["List 3-4 role types this candidate is best suited for"],
    "concerns": ["Data not provided note if any section is missing — never assume negative"]
  }}
}}

IMPORTANT:
1. Return ONLY valid JSON — no markdown, no code blocks, no explanations
2. All text fields must be properly escaped for JSON
3. Use actual data from the candidate's answers
4. Be objective and professional
5. Ensure all boolean values are lowercase (true/false not True/False)
6. If work_experience, education, military, or any field is null or empty — state "not provided" in the relevant field. NEVER assume the candidate lacks experience or education
7. Never say "No prior work experience" or "lacks education" — if the field is empty it simply means data was not collected
8. For certifications, always use the object format with "certificate_name" and "expiry_date". Set "expiry_date" to null always since we do not collect it. Empty array if no certifications mentioned.

Generate the passport profile JSON now:
"""
)