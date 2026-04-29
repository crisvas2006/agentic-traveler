"""
Promo code registry.

Each key is a case-insensitive promo code, and the value is the number
of credits awarded when redeemed.  1 credit = 1 eurocent.

Add new codes here — they are available immediately at runtime.
"""

PROMO_CODES: dict[str, int] = {
    # Referral / social
    "FRIEND": 500,           # €5 — standard friend referral
    "SPECIALFRIEND": 1000,   # €10 — VIP referral
    # Launch & seasonal
    "LAUNCH2026": 300,       # €3 — early adopter launch promo
    "SUMMER2026": 250,       # €2.50 — summer season campaign
    "WANDERLUST": 500,       # €5 — general travel community
    # Engagement
    "FIRSTTRIP": 200,        # €2 — first itinerary reward
    "EXPLORER": 400,         # €4 — power user reward
    "FEEDBACK": 150,         # €1.50 — thank-you for feedback
    # Partnerships
    "HOSTELWORLD": 300,      # €3 — partner promo
    "TRAVELHACK": 500,       # €5 — travel hackathon / event
}
