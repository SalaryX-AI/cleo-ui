"""
Prompts and static messages for the Cleo Interview Scheduling flow.
"""

from langchain.prompts import PromptTemplate


# ── Greeting ──────────────────────────────────────────────────────────────────

INTERVIEW_GREETING_PROMPT = PromptTemplate(
    input_variables=["candidate_name"],
    template=(
        "Hi {candidate_name}! 👋 I'm Cleo, your interview scheduling assistant.\n\n"
        "I'm here to help you lock in your interview slot — it'll only take a minute!"
    )
)

# ── Date selection ────────────────────────────────────────────────────────────

INTERVIEW_ASK_DATE = PromptTemplate(
    input_variables=["dates_list"],
    template=(
        "Please reply with the date that works best for you:\n\n{dates_list}"
    )
)

INTERVIEW_DATE_REASK_PROMPT = PromptTemplate(
    input_variables=["user_input", "dates_list"],
    template=(
        "Sorry, \"{user_input}\" isn't one of the available interview dates.\n\n"
        "Please choose from the dates listed below:\n\n{dates_list}"
    )
)

INTERVIEW_DATE_OFFTOPIC = (
    "Let's stay focused on scheduling your interview! "
    "Please choose one of the available dates listed above."
)

INTERVIEW_NO_SLOTS = PromptTemplate(
    input_variables=["selected_date"],
    template=(
        "It looks like all slots for {selected_date} are already booked. "
        "Please choose a different date from the list above."
    )
)

# ── Slot selection ────────────────────────────────────────────────────────────

INTERVIEW_ASK_SLOT = PromptTemplate(
    input_variables=["selected_date", "slots_list"],
    template=(
        "Great choice! Here are the available time slots for {selected_date}:\n\n"
        "{slots_list}\n\n"
        "Which time works best for you?"
    )
)

INTERVIEW_SLOT_REASK_PROMPT = PromptTemplate(
    input_variables=["user_input", "slots_list"],
    template=(
        "I didn't catch that — you said \"{user_input}\".\n\n"
        "Please choose one of the available time slots:\n\n{slots_list}"
    )
)

INTERVIEW_SLOT_OFFTOPIC = (
    "Let's keep things moving! "
    "Please choose one of the available time slots listed above."
)

# ── Confirmation ──────────────────────────────────────────────────────────────

INTERVIEW_CONFIRM_PROMPT = PromptTemplate(
    input_variables=["candidate_name", "selected_date", "selected_slot", "duration"],
    template=(
        "Perfect! Here's a summary of your interview:\n\n"
        "📅 Date: {selected_date}\n"
        "⏰ Time: {selected_slot}\n"
        "⏱ Duration: {duration} minutes\n\n"
        "Shall I confirm this for you, {candidate_name}? (yes / no)"
    )
)

INTERVIEW_CONFIRM_REASK = (
    "Just to confirm — would you like to go ahead with this slot? "
    "Please reply with yes or no."
)

INTERVIEW_CONFIRM_OFFTOPIC = (
    "I just need a quick yes or no — would you like to confirm this interview slot?"
)

INTERVIEW_RESELECT = (
    "No problem! Let's pick a different time. Here are the available slots again:"
)

# ── Success ───────────────────────────────────────────────────────────────────

INTERVIEW_SUCCESS_PROMPT = PromptTemplate(
    input_variables=["candidate_name", "selected_date", "selected_slot"],
    template=(
        "🎉 You're all set, {candidate_name}!\n\n"
        "Your interview has been confirmed for {selected_date} at {selected_slot}.\n\n"
        "A confirmation email with all the details has been sent to your inbox. "
        "Good luck — we're looking forward to meeting you! 😊"
    )
)

# ── Failure / Edge cases ──────────────────────────────────────────────────────

INTERVIEW_MAX_ATTEMPTS = (
    "I'm having trouble understanding your response. "
    "Please reach out to our team directly to schedule your interview. "
    "Thank you for your patience! 🙏"
)

INTERVIEW_CALENDAR_ERROR = (
    "We ran into a technical issue while confirming your slot. "
    "Our team has been notified and will reach out to you shortly to complete the scheduling. "
    "Sorry for the inconvenience! 🙏"
)

INTERVIEW_NO_DATES = (
    "It looks like there are no available interview dates at the moment. "
    "Our team will reach out to you soon to schedule your interview. "
    "Thank you for your patience! 🙏"
)

# ── Confirmation Email ────────────────────────────────────────────────────────

INTERVIEW_EMAIL_SUBJECT = "Your Interview is Confirmed 🎉"

INTERVIEW_EMAIL_BODY = PromptTemplate(
    input_variables=["candidate_name", "date", "time", "hiring_manager", "duration"],
    template="""Hi {candidate_name},

Your interview has been successfully scheduled! Here are the details:

📅 Date: {date}
⏰ Time: {time}
⏱ Duration: {duration} minutes
👤 Hiring Manager: {hiring_manager}

Please make sure to be available at the scheduled time. If you have any questions or need to make changes, please contact our team directly.

We look forward to speaking with you!

Best regards,
Cleo HR Team"""
)



# ── LLM Prompts ───────────────────────────────────────────────────────────────

PARSE_DATE_PROMPT = PromptTemplate(
    input_variables=["user_input", "available_dates"],
    template="""You are a strict interview date-selection parser.

Your task is to identify which ONE of the available interview dates the candidate selected.

Available dates:
{available_dates}

Candidate response:
"{user_input}"

MATCHING RULES (in priority order):

1. EXACT MATCH — highest priority
   If the candidate's response exactly matches an available date, return that date in YYYY-MM-DD format.

   Example:
   Available: "Sunday, August 09, 2026"
   Candidate: "Sunday, August 09, 2026"
   Output: "2026-08-09"

2. DATE / NAME MATCH
   Match any recognizable date reference to the corresponding available date.
   Treat all of these as equivalent representations of the same date:
   - "August 9", "Aug 9", "Aug 09", "August 09"
   - "9th", "the 9th"
   - "August 9, 2026", "Aug 9 2026", "09 August 2026"
   - "09/08/2026", "2026-08-09"
   - "Sunday" (if only one available date falls on Sunday)

   Examples:
   Candidate: "Aug 9"     → Available: "Sunday, August 09, 2026" → Output: "2026-08-09"
   Candidate: "9th"       → Available: "Sunday, August 09, 2026" → Output: "2026-08-09"
   Candidate: "2026-08-09"→ Available: "Sunday, August 09, 2026" → Output: "2026-08-09"

3. WEEKDAY MATCH
   If the candidate provides only a weekday, match it ONLY if exactly ONE available date has that weekday.
   If multiple available dates share the same weekday, return NO_MATCH.

   Example:
   Available: "Sunday, August 09, 2026" and "Monday, August 10, 2026"
   Candidate: "Monday" → Output: "2026-08-10"
   Candidate: "Sunday" → Output: "2026-08-09"

4. ORDINAL / POSITION MATCH
   Match position-based responses to the corresponding slot in the available-dates list.
   - "first" / "first one" / "first date" / "option 1" / "number 1" → position 1
   - "second" / "second date" / "number 2" → position 2
   - "third" / "number 3" → position 3
   and so on.

5. RELATIVE MATCH
   Match clear relative expressions to the appropriate date:
   - "earliest" / "first available" / "soonest" → first date in the list
   - "latest" / "last one" / "last date" → last date in the list

6. CONVERSATIONAL RESPONSES
   The candidate may include extra words around their date selection.
   Extract the date and ignore irrelevant conversational text.

   Examples:
   Candidate: "Sunday works best for me"      → Output: "2026-08-09"
   Candidate: "I would prefer Monday Aug 10"  → Output: "2026-08-10"
   Candidate: "The second date works for me"  → Output: position 2 date

7. VAGUE / AMBIGUOUS RESPONSES — return NO_MATCH
   If the response is too vague to identify a specific date, return NO_MATCH.
   Do NOT guess.

   Examples that return NO_MATCH:
   - "next week" (no specific date)
   - "soon" (no specific date)
   - "any day" (no specific date)
   - "doesn't matter" (no preference expressed)
   - "asdfgh" (gibberish)
   - A date mentioned that is NOT in the available list

8. DO NOT INVENT A DATE
   Only return a date that exists in the available-dates list.
   A valid calendar date that is not in the list must return NO_MATCH.

IMPORTANT:
- Follow rules in priority order — exact match always wins.
- Never invent, modify, or assume a date not in the available list.
- Return the date in YYYY-MM-DD format only.
- Do not explain your answer.
- Do not return anything except the date or NO_MATCH.

OUTPUT:
Return ONLY the matched date in YYYY-MM-DD format, or ONLY "NO_MATCH"."""
)


PARSE_SLOT_PROMPT = PromptTemplate(
    input_variables=["user_input", "available_slots"],
    template="""You are a strict interview time-slot parser.

Your task is to identify which ONE of the available interview slots the candidate selected.

Available slots:
{available_slots}

Candidate response:
"{user_input}"

MATCHING RULES (in priority order):

1. EXACT MATCH — highest priority
   If the candidate's response exactly matches one of the available slots, return that slot exactly as written.

   Example:
   Available: "3:45-4:30 PM"
   Candidate: "3:45-4:30 PM"
   Output: "3:45-4:30 PM"

2. START-TIME MATCH
   If the candidate provides only a start time, match it to the available slot that begins at that time.
   Treat equivalent time formats as the same: "3:45 PM", "3:45pm", "3:45", "03:45 PM" are all the same.

   Examples:
   Candidate: "3:45 PM" → Available: "3:45-4:30 PM" → Output: "3:45-4:30 PM"
   Candidate: "3:45"    → Available: "3:45-4:30 PM" → Output: "3:45-4:30 PM"

3. ORDINAL / POSITION MATCH
   Match responses that refer to a slot by its position number in the list.
   - "first" / "first one" / "number 1" → slot at position 1
   - "second" / "second slot" / "number 2" → slot at position 2
   - "third" / "number 3" → slot at position 3
   and so on.

4. RELATIVE MATCH
   Match clear relative expressions to the appropriate slot:
   - "earliest" / "first available" → first slot in the list
   - "latest" / "last one" / "last slot" → last slot in the list

5. CONVERSATIONAL RESPONSES
   The candidate may include extra words around their selection.
   Extract the time or slot and ignore irrelevant conversational text.

   Examples:
   Candidate: "3:45-4:30 PM works for me" → Output: "3:45-4:30 PM"
   Candidate: "I'd like the 10 o'clock slot" → Output: slot starting at 10:00
   Candidate: "Can we do 2 PM?" → Output: slot starting at 2:00 PM

6. VAGUE / AMBIGUOUS RESPONSES — return NO_MATCH
   If the candidate uses a vague term that could match multiple slots, return NO_MATCH.
   Do NOT guess or pick the most likely match.

   Examples that return NO_MATCH:
   - "morning" (multiple morning slots available)
   - "afternoon" (multiple afternoon slots available)
   - "any time" (no specific selection)
   - "doesn't matter" (no specific selection)
   - "something early" (too vague)

7. DO NOT INVENT A SLOT
   Only return a slot that actually exists in the available-slots list.
   If the candidate's response does not clearly correspond to any available slot, return NO_MATCH.

IMPORTANT:
- Follow rules in priority order — exact match always wins.
- Return the slot EXACTLY as it appears in the available-slots list.
- Do not explain your answer.
- Do not return anything except the matched slot or NO_MATCH.

OUTPUT:
Return ONLY the matched slot exactly as it appears in the available-slots list, or ONLY "NO_MATCH"."""
)


PARSE_CONFIRMATION_PROMPT = PromptTemplate(
    input_variables=["context", "user_input"],
    template="""Classify whether the user CONFIRMS or DECLINES the action being presented.

CONTEXT (what was just asked):
{context}

USER RESPONSE:
"{user_input}"

RULES:
- YES  → user clearly agrees, confirms, or accepts (yes, sure, correct, go ahead, sounds good, perfect, ok, that works, let's do it)
- NO   → user clearly rejects, declines, or wants to change (no, nope, cancel, change it, pick another, that's wrong, I don't want that)
- UNCLEAR → ambiguous, off-topic, or cannot be determined (maybe, I'm not sure, hmm, what do you mean)

KEY PRINCIPLES:
- Judge the OVERALL INTENT not individual keywords
- "No... wait, yes that's fine" → YES (final intent is confirmation)
- "Yes... actually no, change it" → NO (final intent is rejection)
- "Okay but I'm not sure" → UNCLEAR
- A question like "Can I change it?" → NO
- Do NOT assume confirmation when ambiguous

Return ONLY: YES, NO, or UNCLEAR"""
)


