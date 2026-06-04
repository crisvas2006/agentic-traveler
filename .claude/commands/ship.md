---
description: Pre-commit gate — run the verification gates from CLAUDE.md §2 against the current diff
argument-hint: [optional: spec file path to verify Definition-of-Done against]
---

# /ship — Pre-commit verification gate

The user is about to commit. Run the **required gates** from `@CLAUDE.md §2`
plus the project-specific debris scans, and report a go / no-go decision.
**Do not commit.** Per `CLAUDE.md §9`, the user always runs `git commit` and
`git push` themselves.

Optional spec path: $ARGUMENTS

---

## Procedure

1. **Snapshot the diff.** Run in parallel:
   ```
   git status
   git diff --stat
   git diff
   git diff --cached
   ```

   If nothing has changed, tell the user there's nothing to ship and stop.

2. **Classify the change.** From the diff, decide which gates apply:
   - **Backend touched** = any file under `backend/`.
   - **Frontend touched** = any file under `frontend/`.
   - **Schema touched** = any file under `supabase/`.
   - **Behavior changed** = anything user-visible, a new endpoint, a new
     env var, a setup step change, or any tool/agent addition.

   Skip irrelevant gates — don't make the user wait on `npm run build` for
   a Python-only change.

3. **Run the gates.** Report each as `[PASS]` / `[FAIL]` / `[SKIP]` with
   one-line evidence. Use parallel Bash calls where independent.

   ### Backend gates (if backend touched)

   - **Lint:** run ruff via the project venv:
     `.\backend\.venv\Scripts\python -m ruff check backend\src backend\tests`.
     The venv lives at `D:\Dev\Apps\agentic-traveler\backend\.venv\` — invoke
     it directly rather than relying on an `Activate` call so the gate works
     from any working directory.
   - **Unit tests:** `.\backend\.venv\Scripts\python -m pytest backend\tests -v`.
     Per `backend/TESTING_STRATEGY.md`, integration tests are NOT part of
     this gate (they hit real Gemini + Supabase). If the diff explicitly
     adds an integration test, run only that test under `-m integration`
     with `$env:_INTEGRATION_TESTS="1"`.

   ### Frontend gates (if frontend touched)

   - **Build:** `cd frontend; npm run build`
     This is the canonical "does it ship" check for Next.js — failures
     here mean broken deploy.
   - **Lint:** `cd frontend; npm run lint`

   ### Schema gates (if `supabase/` touched)

   - **RLS check:** every `CREATE TABLE` added in `schema_public.sql` must
     have at least one `CREATE POLICY` (or an explicit `ALTER TABLE … ENABLE
     ROW LEVEL SECURITY` + matching policy) added to `rls_policies.sql` in
     the same diff. Per `CLAUDE.md §8` this is mandatory.
   - **Idempotency:** new statements use `IF NOT EXISTS` / `OR REPLACE`.

   ### Documentation gate (if behavior changed)

   - **README updated:** check `git diff README.md`. If behavior changed and
     `README.md` is not in the diff, that's a `[FAIL]` — per `CLAUDE.md §6`
     this is mandatory. Be lenient only for pure internal refactors that
     don't change setup, commands, or features.

4. **Debris scan** (always run).

   Walk through `git diff` and flag, with file + line:

   - `console.log`, `console.debug`, `console.warn("debug …")`, `debugger;`
   - `pdb.set_trace()`, `breakpoint()`, `pytest.set_trace()`
   - `.only(` or `.skip(` in test files
   - `TODO` / `FIXME` / `XXX` / `HACK` markers added in this diff
     (existing ones are fine — `CLAUDE.md §4` "surgical changes" says don't
     clean up unrelated mess)
   - Commented-out code blocks > 3 lines
   - Plausible secrets: 32+ char hex/base64 literals, anything matching
     `sk-…`, `eyJ…` (JWT-shaped), Telegram bot token shape `\d+:[A-Za-z0-9_-]+`
   - Leftover artifacts: `.env`, `.env.bak`, `*.orig`, `*.rej`, `*.tmp`,
     `nul`, IDE folders
   - `print(` statements in non-script Python (allowed in `scripts/`,
     suspicious elsewhere)
   - New `NEXT_PUBLIC_` env vars referencing a sensitive name (service key,
     resend key, telegram, jwt secret)

5. **Spec adherence** (if `$ARGUMENTS` is a spec path).

   Read the spec and verify its **§11 Definition of Done** checklist
   against the actual diff and gate results. Report each box as
   checked / unchecked. Pay extra attention to:
   - "No file outside §4 was modified — or §10.2 explains why."
     → Diff every changed file against the spec's §4 Files list. Any
     extras must appear in §10.2 with a reason.
   - "All acceptance criteria (§3) pass."
     → For each `AC-N` cross-reference the test or check in §8 and verify
     it's present and passing.

6. **Verdict.** Output a single structured block:

   ```
   ## Ship gate: <GO | NO-GO>

   Touched: backend=<y/n> frontend=<y/n> schema=<y/n> docs=<y/n>

   ### Gates
   - [PASS] Backend lint (ruff)
   - [FAIL] Backend tests — 2 failures in test_credit_manager.py
   - [SKIP] Frontend build (no frontend changes)
   - [PASS] Schema RLS — new table `xyz` has policy in rls_policies.sql
   - [FAIL] README update — `credits/balance` formula changed but README.md not in diff

   ### Debris
   - backend/src/.../tally.py:42 — `print(payload)` left in
   - frontend/src/app/.../page.tsx:118 — `console.log("here")`

   ### Spec adherence (if applicable)
   - DoD 1/9 unchecked: AC-2 has no test
   - File outside §4: backend/src/.../helper.py — not in §10.2 either

   ### Recommendation
   <one paragraph: what to fix before committing, in priority order>
   ```

7. **Don't auto-fix.** Reporting only. The user decides whether to fix or
   ship-anyway. If everything is `[PASS]` and the debris scan is clean,
   say `GO` and remind the user they still own the commit:

   > Gate is green. Commit when ready — I won't do it for you per
   > `CLAUDE.md §9`.
