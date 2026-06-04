---
description: Generate a new task spec under specs/ following task_template_v2.md
argument-hint: <natural language description of the feature or change>
---

# /spec — Create a task spec from a natural language description

The user wants to start a new task. Your job is to produce a complete,
self-contained spec at `specs/task_<feature_name>.md` that strictly follows
the structure in `@task_template_v2.md`. Do **not** start implementing — the
deliverable for this command is the spec file plus a short summary.

User's description:

$ARGUMENTS

---

## Procedure

1. **Read the template.** Open `@task_template_v2.md` and use its structure
   verbatim. Section order and headings must match. Use the same `[REQUIRED]`
   / `[CONDITIONAL]` / `[CLOSING]` tags so the next reader knows what's
   intentional vs. deferred.

2. **Read the project contract.** Skim `@CLAUDE.md` (especially §2 build/test
   commands, §3 conventions, §8 security, §9 never-do list, §10 cost) so the
   spec's §5 Constraints and §6 Edge Cases reflect *this* project's rules,
   not generic ones.

3. **Determine the slug.** Derive `<feature_name>` from the user's
   description: lowercase, snake_case, ≤ 4 words. Check `specs/` for an
   existing file with the same slug and bump with a numeric suffix only if
   needed. The final path is `specs/task_<feature_name>.md`.

4. **Decide if a spec is even warranted.** Per `CLAUDE.md §5`, a spec is
   only required when the task: (a) touches more than one module, (b) is
   expected to take more than ~2 hours, or (c) introduces non-trivial
   mechanisms (async patterns, state machines, external integrations,
   security boundaries, data migrations). If the request is clearly below
   that bar, **say so and ask the user whether to proceed with a spec or
   just implement directly** — don't generate ceremony for a 10-line change.

5. **Ask clarifying questions before writing.** Don't silently fill gaps.
   At minimum ask, when applicable:
   - The user pain or strategic "why now" (drives §1 Problem Statement).
   - Concrete acceptance behaviors (drives §3 — must be testable).
   - What this change explicitly must NOT do (drives §2 Non-Goals + §5
     Constraints).
   - Known boundary inputs or failure modes (drives §6 Edge Cases).
   - Whether the work touches `supabase/schema_public.sql` (drives §9.1
     Data Model & RLS).
   - Whether it adds or modifies an agent / prompt / tool call (drives
     §9.2 LLM Considerations).

   Use the `AskUserQuestion` tool for clarifications with discrete options.
   Open-ended questions can be asked inline.

6. **Fill the spec.** Required sections must all be filled. Conditional
   sections (§9.1 – §9.4) are filled **only** if applicable to this task —
   otherwise omit them entirely (don't leave empty stubs). §10 Findings is
   left empty with a placeholder — it's populated during implementation.

7. **Embed designed artifacts inline.** Per `task_template_v2.md` Golden
   Rule #1, do NOT cross-reference chat or planning docs:
   - LLM prompts → paste full text.
   - JSON schemas, output formats → paste exact schema.
   - Tool / function definitions → full signature + docstring.
   - Data model changes → exact field names and types.
   - RLS policies → SQL inline.

8. **Acceptance criteria must be numbered and testable.** Format as
   `AC-1`, `AC-2`, … Each AC must map to an entry in §8 Testing Plan
   (a unit test, integration test, or concrete manual check). If an AC
   has no possible test or check, rewrite it.

9. **Files & Modules Touched (§4) is your surgical-changes anchor.**
   Use absolute repo paths and tag each as `[create]` / `[modify]` /
   `[delete]`. Don't omit this — implementers compare it against the actual
   diff at review time.

10. **Don't implement.** After the spec is written:
    - Save it to `specs/task_<feature_name>.md`.
    - Return a brief summary covering: the slug used, which conditional
      sections are present and why, any open questions in §12, and the
      one or two highest-risk areas the implementer should pay attention
      to.
    - Ask the user to review and approve before any code is written.

## Quality bar

A spec is good enough to ship when:

- §1 is a real paragraph (≥3 sentences), not a one-liner.
- §3 acceptance criteria are numbered, independently verifiable, and each
  maps to something in §8.
- §4 lists every file you reasonably expect to touch (it's fine to be wrong
  later — §10.2 captures deviations).
- §5 names the project-specific constraints from `CLAUDE.md §9` that apply.
- §6 walks through inputs / concurrency / external failures / partial
  writes / auth+RLS / malformed payloads / idempotency — not all categories
  apply to every task, but you've considered each.
- The conditional sections present are the *right* ones; absent sections are
  absent for a real reason, not because you forgot.

If you can't meet that bar from the user's description alone, ask more
questions before writing.
