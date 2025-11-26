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
    "assistant_manager": {
        "knockout_questions": [
            "Do you have at least 2 years of management or supervisory experience?",
            "Are you available to work flexible hours including nights and weekends?"
        ],
        "questions": [
            "How many years of restaurant management experience do you have?",
            "Have you managed P&L responsibilities before?",
            "Are you experienced in training and developing team members?"
        ],
        "scoring_model": {
            "How many years of restaurant management experience do you have?": {"rule": "Score = years * 5"},
            "Have you managed P&L responsibilities before?": {"rule": "Yes -> 10, No -> 2"},
            "Are you experienced in training and developing team members?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "assistant_store_manager": {
        "knockout_questions": [
            "Do you have at least 1 year of retail or store management experience?",
            "Are you comfortable with inventory management and cash handling?"
        ],
        "questions": [
            "How many years of store operations experience do you have?",
            "Have you supervised a team of 5 or more people?",
            "Are you familiar with daily store opening and closing procedures?"
        ],
        "scoring_model": {
            "How many years of store operations experience do you have?": {"rule": "Score = years * 4"},
            "Have you supervised a team of 5 or more people?": {"rule": "Yes -> 8, No -> 2"},
            "Are you familiar with daily store opening and closing procedures?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "barista": {
        "knockout_questions": [
            "Are you available to work early morning shifts?",
            "Are you comfortable working with coffee equipment and machinery?"
        ],
        "questions": [
            "How many months of barista or beverage preparation experience do you have?",
            "Are you passionate about coffee and creating quality beverages?",
            "Have you worked with espresso machines before?"
        ],
        "scoring_model": {
            "How many months of barista or beverage preparation experience do you have?": {"rule": "Score = months / 2"},
            "Are you passionate about coffee and creating quality beverages?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked with espresso machines before?": {"rule": "Yes -> 5, No -> 2"}
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
    "coffee_specialist": {
        "knockout_questions": [
            "Do you have knowledge of specialty coffee and brewing methods?",
            "Are you comfortable creating latte art and specialty drinks?"
        ],
        "questions": [
            "How many years of specialty coffee experience do you have?",
            "Are you familiar with different coffee origins and flavor profiles?",
            "Have you completed any barista training or certifications?"
        ],
        "scoring_model": {
            "How many years of specialty coffee experience do you have?": {"rule": "Score = years * 4"},
            "Are you familiar with different coffee origins and flavor profiles?": {"rule": "Yes -> 8, No -> 2"},
            "Have you completed any barista training or certifications?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "cook": {
        "knockout_questions": [
            "Do you have a valid food handler's certification or willing to obtain one?",
            "Can you work in a hot kitchen environment?"
        ],
        "questions": [
            "How many years of cooking experience do you have?",
            "Are you comfortable operating grills and fryers?",
            "Have you worked in a professional kitchen before?"
        ],
        "scoring_model": {
            "How many years of cooking experience do you have?": {"rule": "Score = years * 3"},
            "Are you comfortable operating grills and fryers?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a professional kitchen before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "crew_member": {
        "knockout_questions": [
            "Are you able to work flexible hours including evenings and weekends?",
            "Are you comfortable working in a fast-paced environment?"
        ],
        "questions": [
            "How many months of restaurant or food service experience do you have?",
            "Are you willing to learn multiple stations?",
            "Have you worked in customer service before?"
        ],
        "scoring_model": {
            "How many months of restaurant or food service experience do you have?": {"rule": "Score = months / 2"},
            "Are you willing to learn multiple stations?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in customer service before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "customer_support": {
        "knockout_questions": [
            "Do you have excellent communication and problem-solving skills?",
            "Are you comfortable handling customer complaints professionally?"
        ],
        "questions": [
            "How many years of customer service experience do you have?",
            "Have you worked in a customer-facing role before?",
            "Are you comfortable resolving conflicts and de-escalating situations?"
        ],
        "scoring_model": {
            "How many years of customer service experience do you have?": {"rule": "Score = years * 3"},
            "Have you worked in a customer-facing role before?": {"rule": "Yes -> 5, No -> 0"},
            "Are you comfortable resolving conflicts and de-escalating situations?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "dining_room": {
        "knockout_questions": [
            "Are you comfortable maintaining cleanliness standards throughout your shift?",
            "Can you stand and walk for extended periods?"
        ],
        "questions": [
            "How many months of cleaning or dining room experience do you have?",
            "Are you detail-oriented when it comes to cleanliness?",
            "Have you worked in a restaurant dining area before?"
        ],
        "scoring_model": {
            "How many months of cleaning or dining room experience do you have?": {"rule": "Score = months / 2"},
            "Are you detail-oriented when it comes to cleanliness?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a restaurant dining area before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "dishwasher": {
        "knockout_questions": [
            "Are you able to stand for long periods and lift up to 50 lbs?",
            "Are you available to work during peak hours including evenings?"
        ],
        "questions": [
            "How many months of dishwashing or kitchen experience do you have?",
            "Are you comfortable working in hot and wet conditions?",
            "Have you worked in a commercial kitchen before?"
        ],
        "scoring_model": {
            "How many months of dishwashing or kitchen experience do you have?": {"rule": "Score = months / 2"},
            "Are you comfortable working in hot and wet conditions?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a commercial kitchen before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "drive_thru": {
        "knockout_questions": [
            "Do you have clear communication skills and a friendly demeanor?",
            "Are you comfortable multitasking in a fast-paced environment?"
        ],
        "questions": [
            "How many months of drive-thru or customer service experience do you have?",
            "Are you able to take orders accurately while handling payments?",
            "Have you worked with headsets for customer communication?"
        ],
        "scoring_model": {
            "How many months of drive-thru or customer service experience do you have?": {"rule": "Score = months / 2"},
            "Are you able to take orders accurately while handling payments?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked with headsets for customer communication?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "grill_cook": {
        "knockout_questions": [
            "Do you have experience operating commercial grills?",
            "Can you work in a hot kitchen environment with standing for long periods?"
        ],
        "questions": [
            "How many years of grill cooking experience do you have?",
            "Are you familiar with food safety and temperature guidelines?",
            "Have you prepared meats on a commercial grill before?"
        ],
        "scoring_model": {
            "How many years of grill cooking experience do you have?": {"rule": "Score = years * 4"},
            "Are you familiar with food safety and temperature guidelines?": {"rule": "Yes -> 5, No -> 0"},
            "Have you prepared meats on a commercial grill before?": {"rule": "Yes -> 8, No -> 2"}
        }
    },
    "guest_experience": {
        "knockout_questions": [
            "Do you have exceptional customer service skills?",
            "Are you comfortable addressing guest concerns and resolving issues?"
        ],
        "questions": [
            "How many years of customer experience or hospitality experience do you have?",
            "Have you led customer service initiatives before?",
            "Are you skilled at creating positive guest interactions?"
        ],
        "scoring_model": {
            "How many years of customer experience or hospitality experience do you have?": {"rule": "Score = years * 4"},
            "Have you led customer service initiatives before?": {"rule": "Yes -> 8, No -> 2"},
            "Are you skilled at creating positive guest interactions?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "host": {
        "knockout_questions": [
            "Are you comfortable greeting guests and managing seating arrangements?",
            "Do you have a friendly and welcoming demeanor?"
        ],
        "questions": [
            "How many months of hosting or front desk experience do you have?",
            "Are you able to manage wait times and guest flow effectively?",
            "Have you worked in a restaurant front-of-house before?"
        ],
        "scoring_model": {
            "How many months of hosting or front desk experience do you have?": {"rule": "Score = months / 2"},
            "Are you able to manage wait times and guest flow effectively?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a restaurant front-of-house before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "kitchen_staff": {
        "knockout_questions": [
            "Are you willing to work in various kitchen stations?",
            "Do you have basic knowledge of food safety and hygiene?"
        ],
        "questions": [
            "How many months of kitchen or food preparation experience do you have?",
            "Are you comfortable supporting cooks and prep teams?",
            "Have you worked in a commercial kitchen environment before?"
        ],
        "scoring_model": {
            "How many months of kitchen or food preparation experience do you have?": {"rule": "Score = months / 2"},
            "Are you comfortable supporting cooks and prep teams?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a commercial kitchen environment before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "maintenance": {
        "knockout_questions": [
            "Do you have basic maintenance and repair skills?",
            "Are you comfortable troubleshooting equipment issues?"
        ],
        "questions": [
            "How many years of maintenance or facilities experience do you have?",
            "Are you familiar with restaurant equipment maintenance?",
            "Have you worked with HVAC, plumbing, or electrical systems?"
        ],
        "scoring_model": {
            "How many years of maintenance or facilities experience do you have?": {"rule": "Score = years * 4"},
            "Are you familiar with restaurant equipment maintenance?": {"rule": "Yes -> 5, No -> 2"},
            "Have you worked with HVAC, plumbing, or electrical systems?": {"rule": "Yes -> 8, No -> 0"}
        }
    },
    "overnight_crew": {
        "knockout_questions": [
            "Are you available to work overnight shifts regularly?",
            "Are you comfortable working during late night hours?"
        ],
        "questions": [
            "How many months of overnight or late-night shift experience do you have?",
            "Are you reliable and punctual for overnight hours?",
            "Have you worked in a 24-hour operation before?"
        ],
        "scoring_model": {
            "How many months of overnight or late-night shift experience do you have?": {"rule": "Score = months / 2"},
            "Are you reliable and punctual for overnight hours?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a 24-hour operation before?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "prep_cook": {
        "knockout_questions": [
            "Do you have knowledge of food preparation techniques?",
            "Are you available to work early morning shifts for prep work?"
        ],
        "questions": [
            "How many years of food prep or cooking experience do you have?",
            "Are you comfortable following recipes and portion guidelines?",
            "Have you prepared ingredients in a professional kitchen?"
        ],
        "scoring_model": {
            "How many years of food prep or cooking experience do you have?": {"rule": "Score = years * 3"},
            "Are you comfortable following recipes and portion guidelines?": {"rule": "Yes -> 5, No -> 0"},
            "Have you prepared ingredients in a professional kitchen?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "prep_team": {
        "knockout_questions": [
            "Are you able to work as part of a prep team in a fast-paced kitchen?",
            "Do you have basic knife skills and food handling knowledge?"
        ],
        "questions": [
            "How many months of food preparation experience do you have?",
            "Are you comfortable with repetitive prep tasks?",
            "Have you worked in a team-based kitchen environment?"
        ],
        "scoring_model": {
            "How many months of food preparation experience do you have?": {"rule": "Score = months / 2"},
            "Are you comfortable with repetitive prep tasks?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a team-based kitchen environment?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "shift_coordinator": {
        "knockout_questions": [
            "Do you have experience coordinating team activities during shifts?",
            "Are you comfortable delegating tasks and managing workflow?"
        ],
        "questions": [
            "How many years of shift coordination or supervisory experience do you have?",
            "Have you managed restaurant operations during a shift?",
            "Are you skilled at prioritizing tasks and handling pressure?"
        ],
        "scoring_model": {
            "How many years of shift coordination or supervisory experience do you have?": {"rule": "Score = years * 4"},
            "Have you managed restaurant operations during a shift?": {"rule": "Yes -> 8, No -> 2"},
            "Are you skilled at prioritizing tasks and handling pressure?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "shift_lead": {
        "knockout_questions": [
            "Do you have at least 6 months of team leadership experience?",
            "Are you available to work various shifts including evenings and weekends?"
        ],
        "questions": [
            "How many years of shift leadership experience do you have?",
            "Have you supervised a team during restaurant shifts?",
            "Are you comfortable assigning tasks and monitoring performance?"
        ],
        "scoring_model": {
            "How many years of shift leadership experience do you have?": {"rule": "Score = years * 4"},
            "Have you supervised a team during restaurant shifts?": {"rule": "Yes -> 8, No -> 2"},
            "Are you comfortable assigning tasks and monitoring performance?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "shift_leader": {
        "knockout_questions": [
            "Do you have leadership skills and the ability to motivate a team?",
            "Are you available to work flexible hours including opening and closing shifts?"
        ],
        "questions": [
            "How many years of team leadership experience do you have?",
            "Have you led restaurant operations during busy periods?",
            "Are you comfortable handling customer issues and team conflicts?"
        ],
        "scoring_model": {
            "How many years of team leadership experience do you have?": {"rule": "Score = years * 4"},
            "Have you led restaurant operations during busy periods?": {"rule": "Yes -> 8, No -> 2"},
            "Are you comfortable handling customer issues and team conflicts?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "shift_manager": {
        "knockout_questions": [
            "Do you have at least 1 year of management experience?",
            "Are you available to manage any shift including nights and weekends?"
        ],
        "questions": [
            "How many years of restaurant management experience do you have?",
            "Have you managed inventory and labor during shifts?",
            "Are you experienced in training and coaching team members?"
        ],
        "scoring_model": {
            "How many years of restaurant management experience do you have?": {"rule": "Score = years * 5"},
            "Have you managed inventory and labor during shifts?": {"rule": "Yes -> 8, No -> 2"},
            "Are you experienced in training and coaching team members?": {"rule": "Yes -> 5, No -> 0"}
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
    },
    "store_support": {
        "knockout_questions": [
            "Are you able to lift and move products up to 40 lbs?",
            "Are you comfortable with stocking and inventory organization?"
        ],
        "questions": [
            "How many months of retail or stocking experience do you have?",
            "Are you detail-oriented when organizing inventory?",
            "Have you worked in a customer-facing retail environment?"
        ],
        "scoring_model": {
            "How many months of retail or stocking experience do you have?": {"rule": "Score = months / 2"},
            "Are you detail-oriented when organizing inventory?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a customer-facing retail environment?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "team_lead": {
        "knockout_questions": [
            "Do you have leadership qualities and team motivation skills?",
            "Are you comfortable guiding and supporting team members?"
        ],
        "questions": [
            "How many years of team leadership or mentoring experience do you have?",
            "Have you led a team in achieving performance goals?",
            "Are you skilled at providing constructive feedback?"
        ],
        "scoring_model": {
            "How many years of team leadership or mentoring experience do you have?": {"rule": "Score = years * 4"},
            "Have you led a team in achieving performance goals?": {"rule": "Yes -> 8, No -> 2"},
            "Are you skilled at providing constructive feedback?": {"rule": "Yes -> 5, No -> 0"}
        }
    },
    "team_member": {
        "knockout_questions": [
            "Are you able to work flexible hours including weekends?",
            "Are you comfortable performing various restaurant duties?"
        ],
        "questions": [
            "How many months of restaurant or retail experience do you have?",
            "Are you a team player and willing to help where needed?",
            "Have you worked in a fast-paced service environment?"
        ],
        "scoring_model": {
            "How many months of restaurant or retail experience do you have?": {"rule": "Score = months / 2"},
            "Are you a team player and willing to help where needed?": {"rule": "Yes -> 5, No -> 0"},
            "Have you worked in a fast-paced service environment?": {"rule": "Yes -> 5, No -> 2"}
        }
    },
    "trainer": {
        "knockout_questions": [
            "Do you have experience training or mentoring others?",
            "Are you patient and skilled at teaching new concepts?"
        ],
        "questions": [
            "How many years of training or teaching experience do you have?",
            "Have you developed training materials or programs?",
            "Are you comfortable demonstrating procedures and providing feedback?"
        ],
        "scoring_model": {
            "How many years of training or teaching experience do you have?": {"rule": "Score = years * 4"},
            "Have you developed training materials or programs?": {"rule": "Yes -> 8, No -> 2"},
            "Are you comfortable demonstrating procedures and providing feedback?": {"rule": "Yes -> 5, No -> 0"}
        }
    }
}