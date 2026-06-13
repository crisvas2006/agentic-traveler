// profile-questions.ts — the single Traveler-DNA question bank (Task 54).
//
// One source of truth for every question the app may ask to build the "living"
// Traveler DNA. Consumed by the just-in-time elicitation engine (Task 55, a Python
// mirror in backend/.../orchestrator/profile_questions.py kept in sync) and rendered
// through the existing tappable-chip mechanism (SlotRequest.choices, Task 43).
//
// Pure data + types — no React, no lucide imports — so it can be consumed anywhere.
//
// `binding` is the key axis:
//   profile    — a stable trait. Answered once, persisted to
//                user_profiles.profile_data.answered_questions, reused across sagas.
//   flow_state — a current-state question (the "different I's"): re-asked each time
//                the user (re)enters the flow. Never persisted to the durable profile.
//
// This is the SEED set. The nuanced expansion (target ~30–45 questions) is authored
// in Task 59. The seed intentionally includes the small flow_state trio that the
// sagas wire in Tasks 55/56 (trip_intent_this_time, energy_for_this_trip,
// current_craving) so those references resolve before Task 59 lands.

export type QuestionBinding = "profile" | "flow_state";
export type QuestionCategory =
  | "compass"
  | "pulse"
  | "strategy"
  | "identity"
  | "state";

export type ProfileChoice = { id: string; label: string; value: string };

export type ProfileQuestion = {
  id: string; // stable snake_case, e.g. "travel_company"
  binding: QuestionBinding;
  prompt: string; // <= 200 chars, one question
  choices: ProfileChoice[]; // tappable options; [] => free-text only
  allowMulti?: boolean; // e.g. "what makes a trip feel successful"
  informs: string[]; // DNA dimensions / tag families this answer feeds
  category: QuestionCategory;
  cost: "tap" | "flash_lite"; // tap = deterministic write; flash_lite = text parse
  tallyKey?: string; // maps to a legacy Tally form_response key, for backfill (Task 54 §7 Step 8)
  hardOverrideSlot?: string; // if this hard_override slot is set, the question is "covered"
};

export const PROFILE_QUESTIONS: ProfileQuestion[] = [
  // ── profile · compass ──────────────────────────────────────────────────────
  {
    id: "travel_company",
    binding: "profile",
    prompt: "Who's usually in your travel bubble?",
    choices: [
      { id: "solo", label: "Solo — just me", value: "solo" },
      { id: "duo", label: "My partner", value: "duo" },
      { id: "inner_circle", label: "Close friends or family", value: "inner_circle" },
      { id: "socialite", label: "I meet people on the road", value: "socialite" },
    ],
    informs: ["social_energy", "travel_company"],
    category: "compass",
    cost: "tap",
    tallyKey: "travel_bubble",
  },
  {
    id: "trip_success",
    binding: "profile",
    prompt: "What makes a trip feel like a success?",
    choices: [
      { id: "nature", label: "Nature", value: "nature" },
      { id: "culture", label: "Culture & history", value: "culture" },
      { id: "taste", label: "Food & markets", value: "taste" },
      { id: "peace", label: "Peace & reset", value: "peace" },
      { id: "adventure", label: "Adventure", value: "adventure" },
      { id: "aesthetics", label: "Beautiful places", value: "aesthetics" },
      { id: "social", label: "People & nightlife", value: "social" },
      { id: "growth", label: "Learning & growth", value: "growth" },
    ],
    allowMulti: true,
    informs: ["themes", "motivations"],
    category: "compass",
    cost: "tap",
    tallyKey: "trip_success",
  },
  {
    id: "meaning_depth",
    binding: "profile",
    prompt: "How much does the deeper meaning of a place matter to you?",
    choices: [
      { id: "seeker", label: "I seek meaning & connection", value: "seeker" },
      { id: "explorer", label: "I enjoy it, but I'm here for the experience", value: "explorer" },
      { id: "vacationer", label: "I care more about the vibe & fun", value: "vacationer" },
    ],
    informs: ["meaning_depth", "spiritual_interest"],
    category: "compass",
    cost: "tap",
    tallyKey: "meaning_depth",
  },
  {
    id: "immersion",
    binding: "profile",
    prompt: "Where's your sweet spot for local immersion?",
    choices: [
      { id: "deep_end", label: "Eat & stay like a local", value: "deep_end" },
      { id: "best_of_both", label: "Authentic, but a comfy bed", value: "best_of_both" },
      { id: "curated", label: "Curated & high-end", value: "curated" },
    ],
    informs: ["immersion", "comfort_preference"],
    category: "compass",
    cost: "tap",
    tallyKey: "immersion",
  },

  // ── profile · pulse ────────────────────────────────────────────────────────
  {
    id: "morning_vibe",
    binding: "profile",
    prompt: "What's your ideal morning on a trip?",
    choices: [
      { id: "sunrise", label: "Up for the sunrise", value: "sunrise" },
      { id: "civilized", label: "A civilized, slow start", value: "civilized" },
      { id: "night_owl", label: "Mornings are for sleeping", value: "night_owl" },
    ],
    informs: ["daily_rhythm"],
    category: "pulse",
    cost: "tap",
    tallyKey: "ideal_morning",
  },
  {
    id: "activity_intensity",
    binding: "profile",
    prompt: "How much sweat equity are you up for?",
    choices: [
      { id: "leisurely", label: "Leisurely", value: "leisurely" },
      { id: "active", label: "Active", value: "active" },
      { id: "rugged", label: "Rugged", value: "rugged" },
    ],
    informs: ["activity_intensity"],
    category: "pulse",
    cost: "tap",
    tallyKey: "physical_intensity",
  },
  {
    id: "pace",
    binding: "profile",
    prompt: "What's your pace when you travel?",
    choices: [
      { id: "sprinter", label: "See it all (fast)", value: "fast" },
      { id: "wanderer", label: "A bit of both (medium)", value: "medium" },
      { id: "slow_mo", label: "Slow & deep", value: "slow" },
    ],
    informs: ["pace", "energy_strategy"],
    category: "pulse",
    cost: "tap",
    tallyKey: "energy_strategy",
  },

  // ── profile · strategy ─────────────────────────────────────────────────────
  {
    id: "structure_preference",
    binding: "profile",
    prompt: "How much do you like a plan vs. wandering?",
    choices: [
      { id: "total_freedom", label: "Total freedom", value: "total_freedom" },
      { id: "flexible", label: "A loose skeleton", value: "flexible" },
      { id: "planned", label: "Mostly planned", value: "planned" },
    ],
    informs: ["structure_preference", "spontaneity"],
    category: "strategy",
    cost: "tap",
    tallyKey: "solo_freedom",
  },
  {
    id: "risk_appetite",
    binding: "profile",
    prompt: "How much discomfort are you happy to embrace?",
    choices: [
      { id: "comfort_first", label: "Comfort is the priority", value: "comfort_first" },
      { id: "balanced", label: "A bit of friction is fine", value: "balanced" },
      { id: "discomfort_ok", label: "Discomfort is part of the story", value: "discomfort_ok" },
    ],
    informs: ["risk_appetite"],
    category: "strategy",
    cost: "tap",
    tallyKey: "uncertainty_scale",
  },
  {
    id: "adaptability",
    binding: "profile",
    prompt: "A strike cancels your transport. What's your move?",
    choices: [
      { id: "tactician", label: "Find the workaround", value: "tactician" },
      { id: "alchemist", label: "Make it the new plan", value: "alchemist" },
      { id: "delegate", label: "Let me handle it for you", value: "delegate" },
    ],
    informs: ["adaptability"],
    category: "strategy",
    cost: "tap",
    tallyKey: "strike_scenario",
  },
  {
    id: "splurge_priority",
    binding: "profile",
    prompt: "Where does the treat-yourself money usually go?",
    choices: [
      { id: "stay", label: "The stay", value: "stay" },
      { id: "plate", label: "The food", value: "plate" },
      { id: "experience", label: "The experience", value: "experience" },
      { id: "piece", label: "Local craft or art", value: "piece" },
    ],
    informs: ["splurge_priority"],
    category: "strategy",
    cost: "tap",
    tallyKey: "splurge",
  },
  {
    id: "budget_tier",
    binding: "profile",
    prompt: "What's your budget personality?",
    choices: [
      { id: "negotiator", label: "The negotiator", value: "negotiator" },
      { id: "balanced", label: "Balanced", value: "balanced" },
      { id: "high_end", label: "High-end", value: "high_end" },
    ],
    informs: ["budget_tier"],
    category: "strategy",
    cost: "tap",
    tallyKey: "budget_personality",
    hardOverrideSlot: "ask.budget",
  },
  {
    id: "deal_breakers",
    binding: "profile",
    prompt: "Any absolute deal-breakers?",
    choices: [
      { id: "poor_hygiene", label: "Poor hygiene", value: "poor_hygiene" },
      { id: "no_wifi", label: "No Wi-Fi", value: "no_wifi" },
      { id: "crowds", label: "Overwhelming crowds", value: "crowds" },
      { id: "extreme_heat", label: "Extreme heat", value: "extreme_heat" },
      { id: "extreme_cold", label: "Extreme cold", value: "extreme_cold" },
      { id: "poor_transport", label: "Poor transport", value: "poor_transport" },
    ],
    allowMulti: true,
    informs: ["avoids"],
    category: "strategy",
    cost: "tap",
    tallyKey: "deal_breakers",
  },

  // ── flow_state · the "different I's" (re-asked each flow run) ───────────────
  {
    id: "trip_intent_this_time",
    binding: "flow_state",
    prompt: "What are you hoping this trip gives you?",
    choices: [
      { id: "reset", label: "Rest & reset", value: "reset" },
      { id: "adventure", label: "Adventure", value: "adventure" },
      { id: "connection", label: "Connection", value: "connection" },
      { id: "discovery", label: "Discovery", value: "discovery" },
      { id: "everything", label: "A bit of everything", value: "everything" },
    ],
    informs: ["trip_intent"],
    category: "state",
    cost: "tap",
  },
  {
    id: "energy_for_this_trip",
    binding: "flow_state",
    prompt: "How's your energy for this one?",
    choices: [
      { id: "low", label: "Low — keep it gentle", value: "low" },
      { id: "steady", label: "Steady", value: "steady" },
      { id: "high", label: "High — let's go", value: "high" },
    ],
    informs: ["energy_state"],
    category: "state",
    cost: "tap",
  },
  {
    id: "current_craving",
    binding: "flow_state",
    prompt: "Right now, what sounds best?",
    choices: [
      { id: "nature", label: "Nature", value: "nature" },
      { id: "culture", label: "Culture", value: "culture" },
      { id: "food", label: "Food", value: "food" },
      { id: "nightlife", label: "Nightlife", value: "nightlife" },
      { id: "quiet", label: "Quiet", value: "quiet" },
    ],
    informs: ["craving"],
    category: "state",
    cost: "tap",
  },
];

export function profileQuestionById(id: string): ProfileQuestion | undefined {
  return PROFILE_QUESTIONS.find((q) => q.id === id);
}

/** Legal option values for a question — used to re-validate a selection. */
export function legalOptionValues(id: string): Set<string> {
  const q = profileQuestionById(id);
  return new Set((q?.choices ?? []).map((c) => c.value));
}
