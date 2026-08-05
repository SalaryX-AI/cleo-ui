# Job configurations - using job_type as key
# Each job only contains: questions, knockout_questions, scoring_model

JOB_CONFIGS = {
    "null": {
        "questions": [
            "What is your age?",
            "Do you have any experience?",
            "How many years of experience do you have?"
        ],
        "knockout_questions": [
            "Are you legally authorized to work in the U.S.?",
            "Do you have reliable transportation to work?"
        ],
        "scoring_model": {
            "What is your age?": {"rule": "Must be >= 18", "score": 1},
            "Do you have any experience?": {"rule": "Yes -> 10, No -> 0"},
            "How many years of experience do you have?": {"rule": "Score = min(years, 5) * 5"}
        }
    },
    "server": {
        "questions": [
            "We are looking for people with at least one year of server experience. Does that sound like you?",
            "Are you experienced with table service dining standards — things like setting tables for service, attention to detail, and handling multiple courses?",
            "Are you willing to provide friendly, attentive, and personalized service?",
            "Are you comfortable guiding guests through the menu and answering questions about ingredients or pairings?",
            "Our residents are at the heart of everything we do. Are you comfortable and patient when working closely with seniors?",
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Skills — Fine Dining (3) ──────────────────────────────────────────
            "Are you experienced with table service dining standards — things like setting tables for service, attention to detail, and handling multiple courses?": {
                "rule": "Yes -> 3, No -> 0",
                "weight": 3,
                "category": "Skills"
            },

            # ── Culture — Service Attitude (2) ────────────────────────────────────
            "Are you willing to provide friendly, attentive, and personalized service?": {
                "rule": "Yes -> 2, No -> 0",
                "weight": 2,
                "category": "Culture"
            },

            # ── Skills — Menu Knowledge (3) ───────────────────────────────────────
            "Are you comfortable guiding guests through the menu and answering questions about ingredients or pairings?": {
                "rule": "Yes -> 3, No -> 0",
                "weight": 3,
                "category": "Skills"
            },

            # ── Culture — Senior Residents (3) ────────────────────────────────────
            "Our residents are at the heart of everything we do. Are you comfortable and patient when working closely with seniors?": {
                "rule": "Yes -> 3, No -> 0",
                "weight": 3,
                "category": "Culture"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },

            # ── Experience — Server (5) ───────────────────────────────────────────
            "server_experience_years": {
                "rule": "2+ years -> 5, 1-2 years -> 5, 0 years -> 0",
                "weight": 5,
                "category": "Experience"
            },

        },
        "question_acknowledgements": {
            "We are looking for people with at least one year of server experience. Does that sound like you?": "Great — that's a key requirement for this position.",
            "Are you experienced with table service dining standards — things like setting tables for service, attention to detail, and handling multiple courses?": "Perfect — that's exactly what we're looking for.",
            "Are you willing to provide friendly, attentive, and personalized service?": "Noted.",
            "Are you comfortable guiding guests through the menu and answering questions about ingredients or pairings?": "Got it.",
            "Our residents are at the heart of everything we do. Are you comfortable and patient when working closely with seniors?": "Great — that's the heart of what we do.",
        },
        "required_questions": {
            "We are looking for people with at least one year of server experience. Does that sound like you?": {
                "pass_ack": "Great — that's a key requirement for this position.",
                "fail_message": "Thank you for your interest! This role does require at least 1 year of server experience. We'd encourage you to apply again once you've built that experience.",
            }
        },

        "flagged_questions": {
            "Are you experienced with table service dining standards — things like setting tables for service, attention to detail, and handling multiple courses?": {
                "pass_ack":   "Perfect — that's exactly what we're looking for.",
                "flag_reason": "Comfort level with fine dining standards"
            },
            "Are you willing to provide friendly, attentive, and personalized service?": {
                "pass_ack":   "Noted.",
                "flag_reason": "Interpersonal skills concern"
            },
            "Are you comfortable guiding guests through the menu and answering questions about ingredients or pairings?": {
                "pass_ack":   "Got it.",
                "flag_reason": "Menu knowledge concern"
            },
            "Our residents are at the heart of everything we do. Are you comfortable and patient when working closely with seniors?": {
                "pass_ack":   "Great — that's the heart of what we do.",
                "flag_reason": "Culture fit concern"
            }
    }
    
    },

    "painter": {
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    
    "assistant_manager": {
        "questions": [
            "Have you managed P&L responsibilities before?",
            "Are you experienced in training and developing team members?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "assistant_store_manager": {
        "questions": [
            "Have you supervised a team of 5 or more people?",
            "Are you familiar with daily store opening and closing procedures?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "barista": {
        "questions": [
            "Are you passionate about coffee and creating quality beverages?",
            "Have you worked with espresso machines before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "cashier": {
        "questions": [
            "Are you comfortable with basic math and giving accurate change?",
            "Have you worked with point-of-sale systems before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "coffee_specialist": {
        "questions": [
            "Are you familiar with different coffee origins and flavor profiles?",
            "Have you completed any barista training or certifications?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "cook": {
        "questions": [
            "We're looking for someone with at least 3 years of experience as a cook in a professional kitchen. Does that match your background?",
            "Are you comfortable preparing soups, stocks, and sauces, and using methods like braising and roasting with minimal supervision?",
            "Are you comfortable with kitchen math, like scaling recipes and doing simple unit conversions?",
            "Do you have experience maintaining a sanitary workstation and following food safety standards (like ServSafe)?",
            "Are you familiar with preparing therapeutic diets or meals specifically modified for senior residents?",
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {

            # ── Basic Requirements (5 each) ───────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance — Background Check (5) ─────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Experience — Professional Cook 3+ yrs (5) ─────────────────────
            "cook_experience_years": {
                "rule": "3+ years -> 5, 2-3 years -> 3, 1-2 years -> 2, Less than 1 year -> 1, 0 years -> 0",
                "weight": 5,
                "category": "Experience"
            },

            # ── Commitment — Schedule Flexibility (4) ─────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, Partial -> 2, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Compliance — Food & Safety (5) ────────────────────────────────
            "Do you have experience maintaining a sanitary workstation and following food safety standards (like ServSafe)?": {
                "rule": "Yes, certified (ServSafe or equivalent) -> 5, Yes, experienced but not certified -> 3, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Skills — Culinary Technique (5) ───────────────────────────────
            "Are you comfortable preparing soups, stocks, and sauces, and using methods like braising and roasting with minimal supervision?": {
                "rule": "Yes, very comfortable -> 5, Somewhat comfortable -> 3, No -> 0",
                "weight": 5,
                "category": "Skills"
            },

            # ── Skills — Senior Living Dietary Reqs (3) ───────────────────────
            "Are you familiar with preparing therapeutic diets or meals specifically modified for senior residents?": {
                "rule": "Yes, experienced -> 3, Somewhat familiar -> 2, No -> 0",
                "weight": 3,
                "category": "Skills"
            },

            # ── Skills — Kitchen Math (3) ──────────────────────────────────────
            "Are you comfortable with kitchen math, like scaling recipes and doing simple unit conversions?": {
                "rule": "Yes -> 3, Somewhat -> 2, No -> 0",
                "weight": 3,
                "category": "Skills"
            },

            # ── Culture — Senior Fit (2) ───────────────────────────────────────
            "Our residents are seniors with unique needs. Are you patient, attentive, and comfortable working in a senior living environment?": {
                "rule": "Yes -> 2, Somewhat -> 1, No -> 0",
                "weight": 2,
                "category": "Culture"
            },
        },
        "question_acknowledgements": {
            "We're looking for someone with at least 3 years of experience as a cook in a professional kitchen. Does that match your background?": "Great! That 3-year foundation is exactly what we need for our kitchen.",
            "Are you comfortable preparing soups, stocks, and sauces, and using methods like braising and roasting with minimal supervision?": "Perfect. Being able to handle stocks and braising independently is key here.",
            "Are you comfortable with kitchen math, like scaling recipes and doing simple unit conversions?": "Noted.",
            "Do you have experience maintaining a sanitary workstation and following food safety standards (like ServSafe)?": "Got it.",
            "Are you familiar with preparing therapeutic diets or meals specifically modified for senior residents?": "Great! Caring for our residents' unique needs is the heart of our work.",
            "Our residents are seniors with unique needs. Are you patient, attentive, and comfortable working in a senior living environment?": "Wonderful — that kind of care makes all the difference here."
        },

        "required_questions": {
            "We're looking for someone with at least 3 years of experience as a cook in a professional kitchen. Does that match your background?": {
                "pass_ack":     "Great! That 3-year foundation is exactly what we need for our kitchen.",
                "fail_message": "I appreciate your honesty. For this specific role, we require a bit more professional experience. We encourage you to apply again in the future!",
            }
        },

        "flagged_questions": {
            "Are you comfortable preparing soups, stocks, and sauces, and using methods like braising and roasting with minimal supervision?": {
                "pass_ack":    "Perfect. Being able to handle stocks and braising independently is key here.",
                "flag_reason": "Culinary technique comfort level",
                "no_response": "Thank you. Our kitchen relies on those specific techniques for our daily menus, so we're looking for someone already comfortable with them."
            },
            "Are you comfortable with kitchen math, like scaling recipes and doing simple unit conversions?": {
                "pass_ack":    "Noted.",
                "flag_reason": "Basic kitchen math skills",
                "no_response": ""
            },
            "Do you have experience maintaining a sanitary workstation and following food safety standards (like ServSafe)?": {
                "pass_ack":    "Got it.",
                "flag_reason": "Food safety knowledge concern",
                "no_response": ""
            },
            "Are you familiar with preparing therapeutic diets or meals specifically modified for senior residents?": {
                "pass_ack":    "Great! Caring for our residents' unique needs is the heart of our work.",
                "flag_reason": "Therapeutic diet experience",
                "no_response": ""
            },
        },
    },
    "crew_member": {
        "questions": [
            "Are you willing to learn multiple stations?",
            "Have you worked in customer service before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "customer_support": {
        "questions": [
            "Have you worked in a customer-facing role before?",
            "Are you comfortable resolving conflicts and de-escalating situations?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "dining_room": {
        "questions": [
            "Are you detail-oriented when it comes to cleanliness?",
            "Have you worked in a restaurant dining area before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "dishwasher": {
        "questions": [
            "Are you comfortable working in hot and wet conditions?",
            "Have you worked in a commercial kitchen before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "drive_thru": {
        "questions": [
            "Are you able to take orders accurately while handling payments?",
            "Have you worked with headsets for customer communication?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "grill_cook": {
        "questions": [
            "Are you familiar with food safety and temperature guidelines?",
            "Have you prepared meats on a commercial grill before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "guest_experience": {
        "questions": [
            "Have you led customer service initiatives before?",
            "Are you skilled at creating positive guest interactions?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "host": {
        "questions": [
            "Are you able to manage wait times and guest flow effectively?",
            "Have you worked in a restaurant front-of-house before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "kitchen_staff": {
        "questions": [
            "Are you comfortable supporting cooks and prep teams?",
            "Have you worked in a commercial kitchen environment before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "maintenance": {
        "questions": [
            "Are you familiar with restaurant equipment maintenance?",
            "Have you worked with HVAC, plumbing, or electrical systems?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "overnight_crew": {
        "questions": [
            "Are you reliable and punctual for overnight hours?",
            "Have you worked in a 24-hour operation before?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "prep_cook": {
        "questions": [
            "Are you comfortable following recipes and portion guidelines?",
            "Have you prepared ingredients in a professional kitchen?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "prep_team": {
        "questions": [
            "Are you comfortable with repetitive prep tasks?",
            "Have you worked in a team-based kitchen environment?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "shift_coordinator": {
        "questions": [
            "Have you managed restaurant operations during a shift?",
            "Are you skilled at prioritizing tasks and handling pressure?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "shift_lead": {
        "questions": [
            "Have you supervised a team during restaurant shifts?",
            "Are you comfortable assigning tasks and monitoring performance?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "shift_leader": {
        "questions": [
            "Have you led restaurant operations during busy periods?",
            "Are you comfortable handling customer issues and team conflicts?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "shift_manager": {
        "questions": [
            "Have you managed inventory and labor during shifts?",
            "Are you experienced in training and coaching team members?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "shift_supervisor": {
        "questions": [
            "Have you managed a team in a restaurant setting?",
            "Are you comfortable handling customer complaints and team conflicts?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "store_support": {
        "questions": [
            "Are you detail-oriented when organizing inventory?",
            "Have you worked in a customer-facing retail environment?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "team_lead": {
        "questions": [
            "Have you led a team in achieving performance goals?",
            "Are you skilled at providing constructive feedback?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "team_member": {
        "questions": [
            "Are you a team player and willing to help where needed?",
            "Have you worked in a fast-paced service environment?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    },
    "trainer": {
        "questions": [
            "Have you developed training materials or programs?",
            "Are you comfortable demonstrating procedures and providing feedback?"
        ],
        "knockout_questions": [
            "Are you legally allowed to work in the United States?",
            "Are you 18 or older?",
            "We are currently hiring specifically for evening and weekend shifts.  Are you available to work that schedule?",
            "Do you have reliable transportation to and from our location at {address}?"
        ],
        "scoring_model": {
            # ── Basic Requirements (5 each) ──────────────────────────────────────
            "Are you legally allowed to work in the United States?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },
            "Are you 18 or older?": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Basic Requirements"
            },

            # ── Compliance (5) ───────────────────────────────────────────────────
            "background_check_consent": {
                "rule": "Yes -> 5, No -> 0",
                "weight": 5,
                "category": "Compliance"
            },

            # ── Commitment — Schedule (4) ─────────────────────────────────────────
            "We are currently hiring specifically for evening and weekend shifts. Is your general availability a fit for that schedule?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Commitment"
            },

            # ── Logistics — Transportation (4) ────────────────────────────────────
            "Do you have reliable transportation to and from our store located at {address}?": {
                "rule": "Yes -> 4, No -> 0",
                "weight": 4,
                "category": "Logistics"
            },

            # ── Certifications (2) — from ask_certifications node ─────────────────
            "certifications": {
                "rule": "ServSafe/TIPS/Food Safety cert present -> 2, None,no -> 0",
                "weight": 2,
                "category": "Certifications"
            },
        },
    }
}