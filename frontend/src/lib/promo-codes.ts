/**
 * Promo code registry — frontend mirror of
 * `backend/src/agentic_traveler/economy/promo_codes.py`.
 *
 * Each key is a case-insensitive promo code; the value is the number of
 * credits awarded when redeemed. 1 credit = 1 eurocent.
 *
 * KEEP THIS FILE IN SYNC WITH THE BACKEND. When you add a code in Python,
 * add it here too. The Next.js API route validates against this map; the
 * Python backend uses the same map for its own redemption flow.
 */
export const PROMO_CODES: Record<string, number> = {
  // Referral / social
  FRIEND:        500,   // €5  — standard friend referral
  SPECIALFRIEND: 1000,  // €10 — VIP referral
  // Launch & seasonal
  LAUNCH2026:    300,   // €3  — early adopter launch promo
  SUMMER2026:    250,   // €2.50 — summer season campaign
  WANDERLUST:    500,   // €5  — general travel community
  // Engagement
  FIRSTTRIP:     200,   // €2  — first itinerary reward
  EXPLORER:      400,   // €4  — power user reward
  FEEDBACK2026:  100,   // €1  — thank-you for feedback
  // Partnerships
  HOSTELWORLD:   300,   // €3  — partner promo
  TRAVELHACK:    500,   // €5  — travel hackathon / event
};
