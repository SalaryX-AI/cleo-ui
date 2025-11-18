
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
    "carpenter": {
        "knockout_questions": [
            "Are you legally authorized to work in the U.S.?",
            "Do you have reliable transportation to work?"
        ],
        "questions": [
            "What is your age?",
            "Do you have carpentry experience?",
            "How many years of carpentry experience do you have?"
        ],
        "scoring_model": {
            "What is your age?": {"rule": "Must be >= 18", "score": 1},
            "Do you have carpentry experience?": {"rule": "Yes -> 5, No -> 0"},
            "How many years of carpentry experience do you have?": {"rule": "Score = years * 3"}
        }
    },
    "electrician": {
        "knockout_questions": [
            "Are you a licensed electrician?",
            "Are you available to work on-call?"
        ],
        "questions": [
            "How many years of electrical work experience do you have?",
            "Are you familiar with commercial electrical systems?"
        ],
        "scoring_model": {
            "How many years of electrical work experience do you have?": {"rule": "Score = years * 3"},
            "Are you familiar with commercial electrical systems?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "plumber": {
        "knockout_questions": [
            "Are you a licensed plumber?",
            "Do you have reliable transportation?"
        ],
        "questions": [
            "How many years of plumbing experience do you have?",
            "Are you comfortable with emergency calls?"
        ],
        "scoring_model": {
            "How many years of plumbing experience do you have?": {"rule": "Score = years * 3"},
            "Are you comfortable with emergency calls?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "mason": {
        "knockout_questions": [
            "Are you legally authorized to work in the U.S.?",
            "Can you perform heavy lifting?"
        ],
        "questions": [
            "How many years of masonry experience do you have?",
            "Are you experienced with brick and stone work?"
        ],
        "scoring_model": {
            "How many years of masonry experience do you have?": {"rule": "Score = years * 3"},
            "Are you experienced with brick and stone work?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "assembly_line_worker": {
        "knockout_questions": [
            "Are you available to work shifts?",
            "Can you stand for extended periods?"
        ],
        "questions": [
            "Do you have manufacturing experience?",
            "How many months of assembly experience do you have?"
        ],
        "scoring_model": {
            "Do you have manufacturing experience?": {"rule": "Yes -> 5, No -> 0"},
            "How many months of assembly experience do you have?": {"rule": "Score = months / 2"}
        }
    },
    "machinist": {
        "knockout_questions": [
            "Can you read technical blueprints?",
            "Are you available to work overtime?"
        ],
        "questions": [
            "How many years of machinist experience do you have?",
            "Are you familiar with CNC machines?"
        ],
        "scoring_model": {
            "How many years of machinist experience do you have?": {"rule": "Score = years * 3"},
            "Are you familiar with CNC machines?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "welder": {
        "knockout_questions": [
            "Are you a certified welder?",
            "Can you pass a welding test?"
        ],
        "questions": [
            "How many years of welding experience do you have?",
            "What welding techniques are you proficient in?"
        ],
        "scoring_model": {
            "How many years of welding experience do you have?": {"rule": "Score = years * 3"},
            "What welding techniques are you proficient in?": {"rule": "Each technique -> +2 points"}
        }
    },
    "fabricator": {
        "knockout_questions": [
            "Do you have metal fabrication experience?",
            "Are you comfortable with power tools?"
        ],
        "questions": [
            "How many years of fabrication experience do you have?",
            "Are you experienced with sheet metal work?"
        ],
        "scoring_model": {
            "How many years of fabrication experience do you have?": {"rule": "Score = years * 3"},
            "Are you experienced with sheet metal work?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "mechanic": {
        "knockout_questions": [
            "Do you have a valid driver's license?",
            "Are you ASE certified?"
        ],
        "questions": [
            "How many years of automotive experience do you have?",
            "What types of vehicles have you worked on?"
        ],
        "scoring_model": {
            "How many years of automotive experience do you have?": {"rule": "Score = years * 3"},
            "What types of vehicles have you worked on?": {"rule": "Each type -> +2 points"}
        }
    },
    "appliance_repair": {
        "knockout_questions": [
            "Do you have appliance repair experience?",
            "Do you have reliable transportation?"
        ],
        "questions": [
            "How many years of repair experience do you have?",
            "What types of appliances can you repair?"
        ],
        "scoring_model": {
            "How many years of repair experience do you have?": {"rule": "Score = years * 3"},
            "What types of appliances can you repair?": {"rule": "Each appliance type -> +2 points"}
        }
    },
    "cook": {
        "knockout_questions": [
            "Do you have a valid food handler's certification?",
            "Are you available to work evenings and weekends?"
        ],
        "questions": [
            "How many years of professional cooking experience do you have?",
            "What cuisines are you experienced with?"
        ],
        "scoring_model": {
            "How many years of professional cooking experience do you have?": {"rule": "Score = years * 3"},
            "What cuisines are you experienced with?": {"rule": "Each cuisine -> +2 points"}
        }
    },
    "dishwasher": {
        "knockout_questions": [
            "Are you available to work evenings?",
            "Can you work in a fast-paced environment?"
        ],
        "questions": [
            "Do you have restaurant experience?",
            "How many months of kitchen experience do you have?"
        ],
        "scoring_model": {
            "Do you have restaurant experience?": {"rule": "Yes -> 5, No -> 0"},
            "How many months of kitchen experience do you have?": {"rule": "Score = months / 2"}
        }
    },
    "housekeeping": {
        "knockout_questions": [
            "Are you available to work flexible hours?",
            "Can you perform repetitive tasks?"
        ],
        "questions": [
            "Do you have housekeeping experience?",
            "How many months of cleaning experience do you have?"
        ],
        "scoring_model": {
            "Do you have housekeeping experience?": {"rule": "Yes -> 5, No -> 0"},
            "How many months of cleaning experience do you have?": {"rule": "Score = months / 2"}
        }
    }
}