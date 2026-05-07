# AI Task Template

> This template helps you create comprehensive task documents for AI-driven development. Fill out each section thoroughly to ensure the AI agent has all necessary context and can execute the task systematically.

> **Golden Rule: The spec must be self-contained.** An implementer (human or AI)
> must be able to execute the task from this file alone, with zero prior context.
> Never cross-reference a planning document, conversation artifact, or external
> chat. If something was designed during planning (prompts, schemas, configs,
> data models, API contracts), **embed it verbatim here**. Prompts in particular
> capture significant design intent that takes many iterations to reach — do not
> summarize them or reference an external artifact.

## 1. Task Overview
- **Summary:** _Briefly describe the task and desired impact._
- **Background:** _Relevant history, prior attempts, or related work._
- **Primary Owner:** _Who is requesting/approving the work._

## 2. Objectives & Success Criteria
- **Goals:** _Measurable outcomes or KPIs._
- **Non-Goals:** _Explicitly state what is out of scope._
- **Definition of Done:** _Checklist the agent can verify._

## 3. System Context
- **Repositories / Services Affected:** _Name and location of assets._
- **Architecture Notes:** _Key components, data flows, or dependencies._
- **Relevant Specs / Docs:** _Link or embed critical references._

## 4. Constraints & Requirements
- **Technical Constraints:** _Language, frameworks, APIs, performance targets._
- **Operational Constraints:** _Deadlines, environments, approvals._
- **Security / Compliance:** _Data handling, privacy, regulatory notes._

## 5. Inputs & Resources
- **Artifacts Provided:** _Mockups, datasets, configs, credentials._
- **Assumptions:** _What the agent can safely assume is true._
- **Open Questions:** _Items needing clarification._

## 6. Implementation Plan
- **High-Level Steps:** _Ordered list of major milestones._
- **Detailed Tasks:** _Break steps into actionable subtasks with verification steps._
- **Dependencies:** _Tasks or teams that must finish first._

> **Embed designed artifacts inline.** For each component that involves a designed
> artifact, include it directly in the relevant step:
> - **LLM system prompts** — paste the full prompt text, not a summary.
> - **JSON schemas / output formats** — include the exact schema.
> - **Tool definitions** — include the full function signature and docstring.
> - **Data models / config values** — include exact field names and types.
> - **Key behavioral rules** (e.g. personalization, safety, routing rules)
>   — embed them verbatim, not paraphrased.

## 7. Testing & Validation
- **Test Strategy:** _Unit, integration, e2e, or manual validation plan._
- **Acceptance Tests:** _Specific scenarios with expected outcomes._
- **Tooling:** _CI pipelines, test harnesses, or scripts to run._

## 8. Risk Management
- **Known Risks:** _Potential blockers or failure points._
- **Mitigations:** _Fallbacks, monitoring, or escalation paths._
- **Rollback Plan:** _Steps to revert changes if needed._

## 9. Delivery & Handoff
- **Deliverables:** _Artifacts the agent must produce (PRs, docs, builds)._
- **Review Process:** _Reviewers, sign-off steps, demo expectations._
- **Post-Delivery Actions:** _Deployment, monitoring, documentation updates._

## 10. Communication Plan
- **Stakeholders:** _People to update and their preferred channels._
- **Status Cadence:** _Daily standup notes, async updates, or reports._
- **Escalation Path:** _Who to contact for urgent decisions._

## 11. Appendix
- **Glossary:** _Define acronyms or domain-specific terms._
- **Reference Materials:** _Links to tickets, specs, research, or dashboards._
- **Change Log:** _Record iterations of this task document._
