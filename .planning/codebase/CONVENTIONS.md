# Coding Conventions

**Analysis Date:** 2025-02-27

## Naming Patterns

**Files:**
- Python: `snake_case` (e.g., `extraction.py`, `test_repositories.py`, `cost_tracker.py`)
- TypeScript/React: `camelCase` for utilities, `PascalCase` for components (e.g., `useValidationAdmin.ts`, `PipelineStepper.tsx`, `useNavigation.ts`)

**Functions:**
- Python: `snake_case` (e.g., `extraction_node()`, `get_llm_router()`, `should_continue_after_image()`)
- TypeScript: `camelCase` for hooks and utilities (e.g., `useValidationRules()`, `getStageStatus()`)
- Custom decorators: `snake_case` (e.g., `checked()`, `@property`)

**Variables:**
- Python: `snake_case` (e.g., `input_text`, `validation_rule_weights`, `extraction_prompt`)
- TypeScript: `camelCase` (e.g., `currentPath`, `queryKey`, `mutationFn`)
- Constants: `UPPER_SNAKE_CASE` (e.g., `PIPELINE_STAGES`, `EXTRACTION_PROMPT`)

**Types:**
- Python: `PascalCase` for classes, enums (e.g., `GenerationRequest`, `RequestStatus`, `AgentState`)
- TypeScript: `PascalCase` for interfaces, types (e.g., `ValidationRule`, `NavigationState`, `PipelineStepperProps`)
- Python enums inherit from `StrEnum` for string comparison: `class RequestStatus(StrEnum): PENDING = "pending"`

## Code Style

**Formatting:**
- Ruff (Python linter/formatter) with line length 100
- ESLint + TypeScript ESLint for JavaScript/TypeScript
- No Prettier config detected; ESLint handles formatting

**Linting:**
- Python: Ruff with rules `E, F, I, N, W` enabled
  - E: PEP 8 errors
  - F: Pyflakes
  - I: isort (import sorting)
  - N: naming conventions
  - W: PEP 8 warnings
- TypeScript: ESLint recommended + React Hooks plugin
  - `typescript-eslint/recommended` rules enforced
  - React Hooks rules: `exhaustive-deps` warnings

**Import Organization:**

Python order:
1. Standard library (`import asyncio`, `import json`, `from pathlib import Path`)
2. Third-party packages (`from sqlalchemy`, `import pytest`, `from langgraph`)
3. Local modules (`from chronocanvas.agents.state`, `from chronocanvas.db.models`)
4. Ruff handles sorting with `-i` rules

TypeScript order:
1. External packages (`import { useMutation, useQuery }`)
2. Internal API/utils (`import { api }`, `from @/components`)
3. Type imports (`import type { ... }`)

**Path Aliases:**
- TypeScript: `@/*` maps to `./src/*` (e.g., `@/components/ui/badge` → `src/components/ui/badge`)
- Python: No aliases; relative imports from package root (e.g., `from chronocanvas.agents.state`)

## Error Handling

**Patterns:**
- Python: Explicit exception types
  - Built-in: `ValueError`, `RuntimeError`, `TimeoutError`, `PermissionError` (e.g., in `security.py`, `comfyui_client.py`)
  - Custom: `InvariantViolationError(AssertionError)` in `agents/invariants.py` for pipeline contract violations
  - JSON parse failures: try-except with fallback defaults (e.g., `extraction_node` JSON parsing)
  - No generic `Exception` catches; always specific exceptions

- TypeScript: No explicit error type definitions; assume async operations may fail
  - API calls use React Query which handles errors via `useQuery`/`useMutation` error states
  - No throw patterns in component code; errors propagated via state

## Logging

**Framework:** Python stdlib `logging` module

**Patterns:**
- Module-level logger: `logger = logging.getLogger(__name__)`
- Log at appropriate level:
  - `logger.info()`: Major pipeline milestones (e.g., "Extraction agent: extracting figure details")
  - `logger.warning()`: Invariant violations, fallbacks
  - `logger.error()`: Exceptions, failed operations
  - Used in: LLM routing, cost tracking, image generation, embedder, compositing, research cache

- No logging in React components; assume browser console for debugging

## Comments

**When to Comment:**
- Function/class docstrings: Explain purpose and behavior (e.g., `recompile_graph()` in `graph.py`)
- Complex algorithms: Explain why, not what
- Non-obvious state transitions: Document conditional logic
- Ruff directives: Use `# ruff: noqa: <rule>` inline (e.g., `# ruff: noqa: E501` for long lines in prompts)

**JSDoc/TSDoc:**
- Python: Use `"""Docstring"""` format with triple quotes
  - Example: `async def extraction_node(state: AgentState) -> AgentState:`
- TypeScript: Interface/type definitions document themselves via type annotations
  - Props interfaces document component contracts (e.g., `interface PipelineStepperProps`)
  - No JSDoc comments observed in codebase

## Function Design

**Size:** Keep functions focused
- Python nodes: 40-60 lines (e.g., `extraction_node`, `research_node`)
- TypeScript hooks: 10-25 lines for simple queries/mutations
- TypeScript components: 60-100 lines for UI components

**Parameters:**
- Python: Use type hints (e.g., `state: AgentState`, `task_type: TaskType`)
- TypeScript: Always use TypeScript types, not `any`
- Use `**kwargs` or object destructuring sparingly; prefer explicit parameters

**Return Values:**
- Python async nodes: Return updated `AgentState` dict
- TypeScript hooks: Return React Query `UseQueryResult` or `UseMutationResult`
- TypeScript components: Return JSX

## Module Design

**Exports:**
- Python: Use `__all__` to define public API (see `db/models/__init__.py`)
  ```python
  __all__ = [
      "AdminSetting",
      "AuditFeedback",
      ...
  ]
  ```

- TypeScript: Use `export` statements; re-exports via index files
  - Example: `export function useValidationRules() { ... }`

**Barrel Files:**
- Used in `db/models/__init__.py` to centralize imports
- Frontend has component-specific index files (implicit)

## Database & Pydantic

**Pydantic v2:**
- Field defaults: Use `Field(default_factory=...)` for mutable defaults
  - `agent_trace: Mapped[dict | None] = mapped_column(JSONB, default=list)`
  - Use `list` not `[]`

**SQLAlchemy:**
- Model inheritance: `class GenerationRequest(Base, UUIDMixin, TimestampMixin)`
- Mapped columns: `mapped_column(String(50), default=RequestStatus.PENDING, index=True)`
- Use JSONB for postgres; Schema fields use `Mapped[dict | None]`

## TypeScript-Specific

**Strict Mode:** `strict: true` in `tsconfig.json`
- No implicit `any`
- `noUnusedLocals: true`, `noUnusedParameters: true` enforced
- `noUncheckedSideEffectImports: true` for side-effect imports

**Enums:**
- Use `as const` for string literal unions (e.g., `as const` in `PIPELINE_STAGES`)
- Avoid TypeScript enums; prefer const assertions

---

*Convention analysis: 2025-02-27*
