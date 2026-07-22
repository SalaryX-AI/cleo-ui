# Passport configuration — role-agnostic candidate profile builder
# Used by passport_graph.py exclusively

PASSPORT_CONFIG = {

    # ── Eligibility — hard stops, conversation ends on NO ─────────────────────
    "knockout_questions": [
        "To ensure your Passport is legally ready to send to employers, are you legally authorized to work in the United States?",
        "Are you 18 years of age or older?",
        "What is your preferred way to commute (e.g., driving, public transit, or other)?"
    ],

    "knockout_end_messages": {
        "To ensure your Passport is legally ready to send to employers, are you legally authorized to work in the United States?": (
            "Under state and federal regulations, we can only build active Passports for applicants "
            "legally eligible to work in the U.S. Thank you for your honesty, and we wish you the absolute best in your search!"
        ),
        "Are you 18 years of age or older?": (
            "To activate a Universal Candidate Passport across our employer networks, applicants must meet "
            "the minimum safety age requirement of 18. Thank you for your time today!"
        ),
        "What is your preferred way to commute (e.g., driving, public transit, or other)?": (
            "To ensure we can match you with the right opportunities, we need to know your preferred way to commute. "
            "Please reach out to our support team if you have any questions!"
        ),
        
    },

    # ── Role-agnostic screening questions (Q5–Q8) ─────────────────────────────
    "questions": [
        "Let's talk about your background! To find the absolute best matches for you, what kind of work do you have the most experience with? (For example: warehouse, customer service, driving, skilled trades like painting or maintenance, or something else entirely?)",
        "When you think about your day-to-day on those jobs, what were the specific tools, equipment, or tasks you were most comfortable handling independently?",
        "To make sure your Passport stands out to the right hiring teams, do you hold any active licenses, safety cards, or certifications? (Like a driver's license, OSHA, Forklift, or ServSafe?)",
        "Lastly, some roles require active on-your-feet work. Are you comfortable with physical tasks, like standing for most of a shift or lifting up to 50 lbs?",
    ],

    # ── FitScore weights (from spreadsheet) ───────────────────────────────────
    # Weight scale: 1 (low importance) → 5 (critical)
    "scoring_model": {
        "work_authorization":        {"weight": 5, "category": "Basic Requirements"},
        "age_eligibility":           {"weight": 5, "category": "Basic Requirements"},
        "schedule_flexibility":      {"weight": 4, "category": "Commitment"},
        "physical_demands":          {"weight": 5, "category": "Physical/Safety"},
        "relevant_experience":       {"weight": 5, "category": "Experience"},
        "tools_and_equipment":       {"weight": 4, "category": "Skills"},
        "certifications":            {"weight": 3, "category": "Qualifications"},
        "cross_functional_skills":   {"weight": 4, "category": "Skills"},
    },

    # ── Shift preference options (checkbox UI) ────────────────────────────────
    "shift_options": ["Days", "Evenings", "Overnights", "Weekends"],
}