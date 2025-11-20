# Job configurations - using job_type as key
# Each job only contains: questions, knockout_questions, scoring_model

JOB_CONFIGS = {
    "null": {
        "knockout_questions": [
            "Are you legally authorized to work in the U.S.?",
            "Do you have reliable transportation to work?"
        ],
        "questions": [
            "What is your age?",
            "Do you have any experience?",
            "How many years of experience do you have?"
        ],
        "scoring_model": {
            "What is your age?": {"rule": "Must be >= 18", "score": 1},
            "Do you have any experience?": {"rule": "Yes -> 5, No -> 0"},
            "How many years of experience do you have?": {"rule": "Score = years * 3"}
        }
    },
    "front_of_house": {
        "knockout_questions": [
            "Are you available to work evenings and weekends?",
            "Do you have reliable transportation to the restaurant?"
        ],
        "questions": [
            "How many years of customer service experience do you have?",
            "Are you comfortable interacting with customers in a fast-paced environment?",
            "Have you worked in a restaurant before?"
        ],
        "scoring_model": {
            "How many years of customer service experience do you have?": {"rule": "Score = years * 3"},
            "Are you comfortable interacting with customers in a fast-paced environment?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a restaurant before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "line_cook": {
        "knockout_questions": [
            "Do you have a valid food handler's certification?",
            "Can you work in a hot kitchen environment?"
        ],
        "questions": [
            "How many years of cooking experience do you have?",
            "Are you comfortable working under pressure during busy hours?",
            "Have you worked on a line in a professional kitchen?"
        ],
        "scoring_model": {
            "How many years of cooking experience do you have?": {"rule": "Score = years * 3"},
            "Are you comfortable working under pressure during busy hours?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked on a line in a professional kitchen?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "cashier": {
        "knockout_questions": [
            "Are you comfortable handling cash and processing payments?",
            "Are you available to work flexible hours including weekends?"
        ],
        "questions": [
            "How many months of cashier or POS system experience do you have?",
            "Are you comfortable with basic math and giving accurate change?",
            "Have you worked with point-of-sale systems before?"
        ],
        "scoring_model": {
            "How many months of cashier or POS system experience do you have?": {"rule": "Score = months / 2"},
            "Are you comfortable with basic math and giving accurate change?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked with point-of-sale systems before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "shift_supervisor": {
        "knockout_questions": [
            "Do you have at least 1 year of leadership or supervisory experience?",
            "Are you available to work any shift including opening and closing?"
        ],
        "questions": [
            "How many years of team leadership experience do you have?",
            "Have you managed a team in a restaurant setting?",
            "Are you comfortable handling customer complaints and team conflicts?"
        ],
        "scoring_model": {
            "How many years of team leadership experience do you have?": {"rule": "Score = years * 4"},
            "Have you managed a team in a restaurant setting?": {"rule": "Yes -> 10, No -> 3"},
            "Are you comfortable handling customer complaints and team conflicts?": {"rule": "Yes -> 5, No -> 0"}
        }
    }
}