---
description: Project-specific review of the current diff against CLAUDE.md rules and the spec (if any)
argument-hint: [optional: spec file path, e.g. specs/task_foo.md]
---

# /review — Audit the current diff against this project's rules

This is **not** generic code review (use the built-in `/code-review` skill
for correctness bugs and simplification cleanups). This command audits the
working tree against the **project-specific** rules in `@CLAUDE.md` and,
if provided, the acceptance criteria and Files-Touched list of a spec.

Optional spec path: $ARGUMENTS

---

## Procedure

1. **Gather the diff.** Run:
   ```
   git status
   git diff --stat
   git diff
   git diff --cached
   ```
   If there are no changes, stop and tell the user.

2. **Load context.** Read `@CLAUDE.md`. If `$ARGUMENTS` names a spec file,
   read it too — you'll compare the diff against §3 (acceptance criteria)
   and §4 (files touched).

3. **Run the audit.** Go through each checklist item below against the
   actual diff. For each finding, report: file + line, severity (BLOCK /
   WARN / INFO), what's wrong, and the fix.

### Hard blocks (project never-do rules — `CLAUDE.md §9`)

- [ ] No frontend deps appearing in `backend/pyproject.toml` or
      `backend/requirements.txt`, and no Python in `/frontend/`.
- [ ] No real Gemini / Telegram API calls in `backend/tests/` (must be
      mocked per `backend/TESTING_STRATEGY.md`).
- [ ] No `--no-verify`, `--amend`, `--force` on git in the diff or new scripts.
- [ ] No commit / push commands wired into automation.
- [ ] No new Supabase tables without an RLS policy in the same diff
      (check `supabase/rls_policies.sql` and `supabase/schema_public.sql`).
- [ ] No bypass of RLS in application code (raw service-key reads of
      user-scoped data without a documented reason in the spec).
- [ ] No hardcoded secrets — API keys, tokens, passwords, bot tokens,
      JWT secrets, Supabase service keys. Check for literal-looking values
      and for env-var loads being skipped.
- [ ] No new `NEXT_PUBLIC_` prefix on a sensitive env var
      (Supabase service key, Resend key, Telegram token, etc.).
- [ ] No logs that include: full bot tokens, Supabase service keys, JWTs,
      phone numbers, email bodies, user PII beyond user_id.

### Backend rules

- [ ] New / changed Python code targets 3.13 syntax — matches `backend/Dockerfile`.
- [ ] If `requirements.txt` changed, versions are pinned (no bare
      `package` lines).
- [ ] New / changed routes are under `backend/src/agentic_traveler/interfaces/routers/`.
- [ ] New tools live under `backend/src/agentic_traveler/tools/` and follow
      `AGENTIC_GUIDELINES.md` — one tool = one clear action, documented
      name and docstring.
- [ ] New / modified agents follow `AGENTIC_GUIDELINES.md` — small,
      specialized, minimal context, model tier matches the
      `CLAUDE.md §10` cost-awareness rule (default to flash-lite unless
      reasoning quality demands flash).
- [ ] User input that flows into an LLM prompt is sanitized
      (`agentic_traveler/core/` or equivalent) — prompt-injection surface.
- [ ] New code paths that can fail in production have structured logs
      with user_id + intent + timing.
- [ ] Tests exist for new behavior (unit at minimum; integration if the
      change touches Supabase or the Gemini API).

### Frontend rules

- [ ] If a `lg:` Tailwind class was added, a matching `sm:` / `md:`
      treatment was added in the same diff. Mobile-first is non-negotiable
      (`CLAUDE.md §3`).
- [ ] No external API calls from a client component / browser.
      Client → Next.js Route Handler → external. Check for
      `fetch('https://...')` outside `src/app/api/` and outside server actions.
- [ ] If `shadcn/ui` components were added: only the components actually
      used, not the whole library; `components/ui/` files are committed.
- [ ] React 19 / Next 16 patterns — read `frontend/AGENTS.md` before
      flagging anything that "looks wrong" by older Next.js conventions.

### Supabase / data

- [ ] Schema changes are idempotent (`IF NOT EXISTS`, safe-to-rerun).
- [ ] New tables have an RLS policy in `supabase/rls_policies.sql` in the
      same diff.
- [ ] User-scoped tables use the `auth.uid() = user_id` pattern unless the
      spec justifies otherwise.
- [ ] No `gen_random_uuid()` default removed on a PK without a reason.
- [ ] No fields removed from existing models without explicit approval
      (`CLAUDE.md §8`).

### Documentation

- [ ] If a feature or setup step changed, `README.md` was updated in the
      same diff (`CLAUDE.md §6` — mandatory).
- [ ] No new `*.md` files created without the user explicitly asking
      (`CLAUDE.md §6`).

### Spec adherence (only if $ARGUMENTS is a spec path)

- [ ] Every acceptance criterion in §3 of the spec has a corresponding
      test, manual check, or visible code change in the diff.
- [ ] Every file in the diff appears in §4 of the spec, OR is recorded
      in §10.2 Spec deviations with a reason.
- [ ] Edge cases in §6 are addressed (or the spec was updated in §10.2 to
      defer them).
- [ ] §11 Definition of Done items all pass (run `ruff check`, `pytest`,
      `npm run build` as relevant — report results).

### Stray-debris scan

- [ ] No `console.log`, `console.debug`, `console.error("DEBUG ...")`,
      `debugger;`, `pdb.set_trace()`, `breakpoint()`, `pytest.set_trace()`
      added.
- [ ] No `.only(` / `.skip(` left in tests.
- [ ] No TODO / FIXME / XXX added without a tracking note (a spec
      reference or a §10.1 entry is fine).
- [ ] No commented-out code blocks larger than 3 lines.
- [ ] No leftover dev artifacts (`.env.bak`, `*.tmp`, `nul`,
      `*.orig`, IDE folders).

4. **Report.** Output a structured summary:

   ```
   ## Review summary

   Blocks: <count>   Warnings: <count>   Info: <count>

   ### BLOCK
   - <file>:<line> — <issue>. Fix: <fix>.

   ### WARN
   - …

   ### INFO
   - …

   ### Verified clean
   - <areas checked with no findings — short list, not exhaustive>
   ```

5. **Don't fix.** Reporting only. If the user wants the issues addressed,
   they'll ask. The exception: if a finding is a one-character typo whose
   fix is uncontroversial, mention it but still don't apply it without
   permission.
