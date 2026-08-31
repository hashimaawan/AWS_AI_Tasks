# Inputs + expected answers for all three challenges.
# Data lives here; grading logic lives in grading.py; orchestration in run_comparison.py.

STRUCTURED_INSTRUCTIONS = """Extract these fields from the support email and return
ONLY a JSON object — no prose, no markdown fences:
{"customer_name": string, "issue": string,
 "sentiment": "positive"|"neutral"|"negative",
 "urgency": "low"|"medium"|"high"}"""

STRUCTURED_SCENARIOS = [
    {
        "id": "billing_double_charge",
        "email": """From: maria.gomez@example.com
Subject: URGENT - charged twice and no one is helping

Hi, I'm Maria Gomez. I was billed TWICE for my annual plan on March 3rd
(order #A-99182). I've emailed support twice this week with no reply and
I'm honestly furious. If this isn't fixed today I'm disputing the charge
with my bank and cancelling. Please refund the duplicate immediately.""",
        "expected": {"sentiment": "negative", "urgency": "high",
                     "name_contains": "Maria", "issue_must_include": ["A-99182"]},
    },
    {
        "id": "feature_praise",
        "email": """From: tom.baker@example.com
Subject: Love the new dashboard

Hi, this is Tom Baker. Just wanted to say I really love the new dashboard —
great work! One small thing: could you add a dark mode at some point?
Totally not urgent, whenever you get to it. Thanks again!""",
        "expected": {"sentiment": "positive", "urgency": "low",
                     "name_contains": "Tom", "issue_must_include": ["dark mode"]},
    },
    {
        "id": "shipping_delay",
        "email": """From: david.chen@example.com
Subject: Where is my order?

Hello, David Chen here. My order (#SH-4471) was supposed to arrive last
Tuesday, but the tracking hasn't updated in 5 days. I need it before the
weekend as it's a gift. Could you please check what's going on?""",
        # Relabelled medium->high: all 4 models independently said "high" for a
        # 5-day-stalled gift with a weekend deadline. The models were more defensible
        # than the original label. Stays in the low-trust "subjective" tier regardless.
        "expected": {"sentiment": "negative", "urgency": "high",
                     "name_contains": "David", "issue_must_include": ["SH-4471"]},
    },
]

REASONING_SCENARIOS = [
    {
        "id": "coffee_price",
        "problem": """A coffee shop sells 180 cups/day at $4.50 each, 6 days/week.
Beans cost $0.80/cup; fixed weekly costs are $1,900. The owner considers raising
the price to $5.00, which market tests suggest drops volume by 12%.
Should they raise the price? Show weekly profit before and after,
then give a one-line recommendation.""",
        "expected": {"figures": [(2096, 2), (2091.68, 2)],
                     "recommendation_keywords": ["do not raise", "don't raise", "not raise",
                        "keep the price", "maintain", "not recommend", "against raising"]},
    },
    {
        "id": "gym_price_cut",
        "problem": """A gym has 300 members paying $40/month. Each member costs $5/month
to service, and fixed monthly costs are $6,000. Management considers cutting the price
to $30/month, which marketing estimates will grow membership by 15%.
Should they cut the price? Show monthly profit before and after,
then give a one-line recommendation.""",
        "expected": {"figures": [(4500, 5), (2625, 5)],
                     "recommendation_keywords": ["do not cut", "don't cut", "not cut",
                        "keep the price", "maintain", "not recommend", "against cutting"]},
    },
    {
        "id": "vendor_switch",
        "problem": """A SaaS company pays $8,000/month for a vendor tool. An alternative
costs $3,000/month plus a one-time $12,000 migration fee. Over a 12-month horizon,
is switching worth it? Show the total 12-month cost of each option,
then give a one-line recommendation.""",
        # Deliberate trap: correct answer is "switch" (the only non-"don't change" case),
        # so a model that lazily pattern-matches "no" is exposed here.
        "expected": {"figures": [(96000, 50), (48000, 50)],
                     "recommendation_keywords": ["switch", "migrate", "worth it",
                        "should switch"]},
    },
]

TONE_SCENARIOS = [
    {"id": "cloud_computing", "concept": "cloud computing"},
    {"id": "what_is_api", "concept": "what an API is"},
    {"id": "machine_learning", "concept": "machine learning"},
]