# Proposal — Destination Knowledge Corpus (runtime RAG, post-validation)

> Status: **FUTURE / NOT SCHEDULED.** Companion to
> `specs/task_45_advisor_core.md`. Ratified direction (2026-06-10 brainstorm):
> distilled frameworks in prompts NOW; this document is the base for the
> retrieval-backed evolution once the advisor behavior is validated with
> users. Not a task spec — when scheduled, derive a `task_<n>` spec from it
> per `task_template_v2.md`.

## 1. Why (later)

Task 45 grounds advisory turns in (a) framework blocks distilled into prompts
and (b) per-trip cached destination briefs generated from model parametric
knowledge. That is cheap and good enough to validate the advisor product.
Its ceiling: parametric knowledge drifts, can't cite, can't cover niche
destinations deeply, and every improvement requires a prompt release. A
retrieval corpus lifts that ceiling: curated travel material retrieved at
brief-capture time (not per turn), giving deeper, citable, updatable
knowledge without touching prompts.

## 2. Trigger conditions (when to schedule this)

Schedule only when ALL of:
- Advisor validated: proposal acceptance rate (task 45 KPI) is measured and
  the advisor is a retained behavior, not an experiment.
- Observed knowledge failures: a log of brief inaccuracies / thin coverage
  exists (collect via stream-B judge or user feedback) justifying retrieval.
- Unit economics known: per-trip LLM cost from metrics_daily shows headroom
  for embedding + retrieval infrastructure.

## 3. Shape (initial position, to be re-derived at scheduling time)

- **Retrieval point:** brief capture only — the corpus feeds
  `capture_destination_brief`, NOT per-turn composer calls. Keeps the task-45
  architecture intact: the composer still reads one cached brief; only the
  brief gets smarter. This is the key compatibility decision.
- **Corpus content (licensing-aware):** public-domain and licensed-clean
  sources only — national tourism board open data, Wikivoyage (CC BY-SA,
  attribution required), WMO/climate normals for seasonality, curated
  in-house destination notes. Explicitly NOT: scraping guidebooks (Lonely
  Planet et al.) — their *frameworks* are already distilled into prompts;
  their *text* is copyrighted.
- **Storage:** Supabase pgvector on the existing project (free-tier
  discipline: corpus is world data, one shared table, no RLS-per-user;
  growth view `vw_corpus_growth` in the same migration per CLAUDE.md §10).
- **Pipeline:** offline ingestion script (chunk → embed → upsert), not a
  runtime crawler. Embeddings via the cheapest adequate Gemini embedding
  model at scheduling time.
- **Brief capture change:** retrieve top-k chunks for the destination,
  inject as context, require the model to ground `best_windows` /
  `signature_experiences` in them, store source attributions in the brief
  (`sources: [...]`) → renders as citations under the disclaimer.

## 4. Non-goals (standing)

- No per-turn retrieval (latency + cost).
- No user-generated content in the corpus v1.
- No claim of authority — the "verify with official sources" disclaimer
  rule survives retrieval (CLAUDE.md §7.1).

## 5. Open questions to resolve at scheduling time

- Wikivoyage attribution rendering in chat UI (CC BY-SA share-alike scope).
- Corpus refresh cadence and staleness marking per chunk.
- Whether mood→destination matching material (stream-B research) belongs in
  the corpus or stays prompt-distilled.
