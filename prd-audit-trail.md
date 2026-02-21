# PRD: Audit Trail for ChronoCanvas Pipeline

## Problem

ChronoCanvas generates portraits through a 7-agent LLM pipeline, but provides no meaningful visibility into what each agent actually did. Raw LLM prompts and responses are discarded after parsing, validation gives a numeric score with no reasoning, and the frontend shows only tiny cost badges. Users cannot debug bad outputs or trace the decision chain from input to final image.

## Goals

1. **Full LLM visibility** — Store and display the exact system prompt, user prompt, and raw response for every agent LLM call.
2. **Validation reasoning** — Each validation category score includes 2-4 sentences explaining why the score was given.
3. **Pipeline traceability** — A visual pipeline stepper replaces flat agent badges, showing status, duration, cost, and output summary per stage.
4. **Dedicated audit views** — An inline summary on the Generate page plus a full-page audit detail view at `/audit/:id` and a list view at `/audit`.

## User Stories

- As a user, I want to see exactly what prompts were sent to each LLM agent so I can debug poor outputs.
- As a user, I want to understand why the validator gave a particular score so I can iterate on my input.
- As a user, I want to see a timeline of which pipeline stages ran, how long each took, and what they cost.
- As a user, I want to browse past generations and drill into the full audit trail for any of them.

## Scope

### Backend

- **LLMResponse enrichment** — Add `system_prompt`, `user_prompt`, `duration_ms` fields to `LLMResponse`.
- **Router timing** — Wrap provider calls with timing; attach prompts and duration to response.
- **AgentState.llm_calls** — New list field accumulating per-call records: agent, timestamp, prompts, raw response, parsed output, provider, model, tokens, cost, duration.
- **Node updates** — Each LLM-calling node (extraction, research, prompt_generation, validation) appends a call record after every `llm_router.generate()`.
- **Validation reasoning** — Updated validation prompt requiring per-category `reasoning` and `overall_reasoning`.
- **Database** — `llm_calls JSONB` column on `generation_requests`; `reasoning TEXT` column on `validation_results`.
- **Persistence** — `llm_calls` from final pipeline state saved to the generation request record.
- **Audit API** — `GET /api/generate/{request_id}/audit` returns full audit detail including LLM calls, validation reasoning, images, and metadata.

### Frontend

- **Types** — `LLMCallDetail`, `ValidationCategoryDetail`, `AuditDetail` interfaces.
- **Hook** — `useAuditDetail(id)` fetching from the audit endpoint.
- **PipelineStepper** — Vertical stepper component showing pipeline stages with status icons, agent names, durations, costs, and one-line output summaries.
- **Generate page** — Replace agent trace badges with PipelineStepper; add "View Full Audit" link.
- **AuditDetail page** (`/audit/:id`) — Header, pipeline timeline, expandable LLM call cards (system prompt, user prompt, raw response, parsed output), validation section with reasoning, generated image display.
- **AuditList page** (`/audit`) — Table of recent generations linking to detail pages.
- **Routing & navigation** — New routes and sidebar nav item for Audit.

## Non-Goals

- Real-time streaming of LLM calls during generation (existing WebSocket progress is sufficient).
- Audit trail for non-LLM operations (image generation, export).
- User authentication or access control for audit data.
- Retention policies or data cleanup for audit records.

## Success Criteria

1. Every LLM call in the pipeline is captured with full prompt/response text.
2. Validation results include human-readable reasoning per category.
3. The audit detail page displays all captured data in an organized, expandable layout.
4. The pipeline stepper provides at-a-glance status for each generation stage.
5. Docker build passes successfully with all changes.
