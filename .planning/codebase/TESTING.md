# Testing Patterns

**Analysis Date:** 2025-02-27

## Test Framework

**Runner:**
- pytest 8.0.0+ with asyncio support
- Config: `backend/pyproject.toml` under `[tool.pytest.ini_options]`
  - `asyncio_mode = "auto"` — automatically handles async test functions
  - `testpaths = ["tests", "../tests"]` — discovers tests in both locations

**Assertion Library:**
- Built-in `assert` statements (no pytest-assert-rewrite special handling)

**Run Commands:**
```bash
pytest                    # Run all tests in tests/ and ../tests/
pytest -v               # Verbose output with test names
pytest tests/test_agents/ # Run specific test module
pytest -k test_valid    # Run tests matching pattern
pytest --cov           # Generate coverage report (requires pytest-cov)
pytest -x              # Stop on first failure
```

## Test File Organization

**Location:**
- Root-level `tests/` directory (not co-located with source)
- Mirror source structure: `tests/test_agents/`, `tests/test_api/`, `tests/test_db/`, `tests/test_integration/`, `tests/test_llm/`
- Backend tests: `backend/tests/` for minimal fixtures (e.g., `test_content_moderation.py`)

**Naming:**
- Test modules: `test_*.py` (e.g., `test_state.py`, `test_decisions.py`, `test_health.py`)
- Test functions: `test_*()` (e.g., `test_agent_state_creation()`)
- Test classes: `Test*` for grouped test suites (e.g., `class TestStateValidators:`)

**Structure:**
```
tests/
├── conftest.py              # Global fixtures
├── test_agents/             # Agent pipeline tests
│   ├── __init__.py
│   ├── test_invariants.py   # Contract/precondition tests
│   ├── test_state.py        # State TypedDict validation
│   ├── test_decisions.py    # Conditional edge functions
│   ├── test_face_swap.py    # Facial compositing
│   ├── test_mock_imaging.py # Image generation
│   └── test_export_face_swap.py
├── test_api/                # API endpoint tests
│   ├── __init__.py
│   ├── test_health.py       # Health check endpoint
│   ├── test_agents_api.py   # Agent list/cost endpoints
│   ├── test_generation_face.py  # Generation with face swap
│   ├── test_websocket.py    # WebSocket progress streaming
│   └── test_faces_upload.py # File upload handling
├── test_db/                 # Database & ORM tests
│   ├── __init__.py
│   └── test_repositories.py # Repository CRUD operations
├── test_integration/        # Full pipeline tests
│   ├── __init__.py
│   ├── test_graph_build.py  # Graph construction
│   └── test_checkpoint_recovery.py  # Retry/recovery logic
└── test_llm/                # LLM provider tests
    ├── __init__.py
    ├── test_cost_tracker.py
    └── test_rate_limiter.py
```

## Test Structure

**Suite Organization:**
```python
# Unit test example (test_decisions.py)
def test_continue_after_image_success():
    state = {"error": None}
    assert should_continue_after_image(state) == "validate"

# Class-based suite (test_invariants.py)
class TestStateValidators:
    def test_valid_initial_state_passes(self):
        validate_initial_state(make_state())

    @pytest.mark.parametrize("field", ["request_id", "input_text"])
    def test_missing_required_string(self, field):
        state = make_state()
        del state[field]
        with pytest.raises(InvariantViolationError, match=field):
            validate_initial_state(state)

# Async test (test_repositories.py)
@pytest.mark.asyncio
async def test_create_and_get_figure(db_session):
    repo = FigureRepository(db_session)
    figure = await repo.create(name="Test Figure")
    await db_session.flush()
    assert figure.id is not None
```

**Patterns:**
- **Setup:** Use fixtures (see Fixtures & Factories below)
- **Teardown:** pytest automatically cleans up fixtures; manual cleanup with `shutil.rmtree()`
- **Assertion:** Plain `assert` statements with context (e.g., `assert figure.name == "Test Figure"`)
- **Parameterization:** `@pytest.mark.parametrize("field", [...])` for multiple inputs

## Mocking

**Framework:** Python `unittest.mock` (standard library)

**Patterns:**
```python
from unittest.mock import AsyncMock, MagicMock, patch

# Mock async functions
mock_image_repo = AsyncMock()
mock_graph.aget_state = AsyncMock(return_value=MagicMock(values={}))

# Mock external services
with patch("chronocanvas.services.generation.ProgressPublisher", return_value=AsyncMock()):
    # Test code

# Check calls
mock_graph.aupdate_state.assert_called_once()
```

**What to Mock:**
- External APIs (LLM providers, image generation services)
- Database queries (use `db_session` fixture instead for integration tests)
- WebSocket connections (`AsyncMock()` for publishers)
- Time-dependent operations (e.g., rate limiters)

**What NOT to Mock:**
- Database operations in DB tests — use real in-memory SQLite
- Graph state transitions — test with real `build_graph()`
- Validation logic — test with real validators, not mocked results

## Fixtures and Factories

**Test Data:**
```python
# Fixture-based (conftest.py)
@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture
async def db_session(db_engine):
    session_factory = async_sessionmaker(db_engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session

# Factory function (test_invariants.py)
def make_state(**overrides) -> dict:
    base = {
        "request_id": "req-001",
        "input_text": "Napoleon Bonaparte in battle",
        "agent_trace": [],
        "llm_calls": [],
        "retry_count": 0,
    }
    base.update(overrides)
    return base

def make_llm_call(**overrides) -> dict:
    base = {
        "agent": "extraction",
        "timestamp": time.time(),
        "provider": "ollama",
        "model": "llama3.1:8b",
        "input_tokens": 120,
        "output_tokens": 80,
        "cost": 0.0,
        "duration_ms": 450,
    }
    base.update(overrides)
    return base
```

**Location:**
- Global fixtures in `tests/conftest.py`
- Test-module-specific fixtures in module-level conftest or inline with `@pytest.fixture`
- Factory functions defined in test classes (e.g., `make_state()` in `test_invariants.py`)

## Coverage

**Requirements:** No enforced coverage targets; manual review

**View Coverage:**
```bash
pytest --cov=chronocanvas --cov-report=html
# Opens coverage report in htmlcov/index.html
```

**Current Status:** 152 tests passing as of latest run

## Test Types

**Unit Tests:**
- Scope: Single function/method in isolation
- Approach: Test pure functions with fixed inputs/outputs
- Examples:
  - `test_continue_after_image_success()` — decision functions
  - `test_agent_state_creation()` — TypedDict validation
  - `test_cost_tracker()` — LLM cost calculations

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Use real DB, real graph structure; mock external APIs
- Examples:
  - `test_graph_builds_successfully()` — graph construction
  - `test_create_and_get_figure()` — repository + DB operations
  - `test_retry_uses_minimal_reset_when_checkpoint_alive()` — recovery logic

**End-to-End Tests:**
- Framework: Not currently used; Playwright available in frontend devDeps
- Current approach: Integration tests serve as pseudo-E2E for API validation

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_retry_falls_back_to_db_when_checkpoint_missing():
    mock_session = AsyncMock()
    mock_repo = AsyncMock()

    coordinator = RetryCoordinator()
    result = await coordinator.rebuild_state_from_db(request_id, mock_session, mock_repo)

    mock_repo.get.assert_called_once_with(request_id)
```

**Error Testing:**
```python
@pytest.mark.parametrize("field", ["request_id", "input_text"])
def test_missing_required_string(self, field):
    state = make_state()
    del state[field]
    with pytest.raises(InvariantViolationError, match=field):
        validate_initial_state(state)

# Match regex in error message
with pytest.raises(ValueError, match="must be positive"):
    some_function(-1)
```

**Database Testing:**
```python
@pytest.mark.asyncio
async def test_create_generation_request(db_session):
    repo = RequestRepository(db_session)
    request = await repo.create(input_text="Test prompt", status="pending")
    await db_session.flush()  # Flush to ensure DB writes before assertions

    fetched = await repo.get(request.id)
    assert fetched is not None
    assert fetched.input_text == "Test prompt"
```

**API Testing:**
```python
@pytest.mark.asyncio
async def test_health_endpoint():
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        response = await client.get("/api/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
```

## Known Test Limitations

**SQLite Incompatibilities:**
- Pre-existing failures in `test_db/test_repositories.py` due to JSONB columns not supported by SQLite
- Tests use SQLite for speed; JSONB features tested in integration tests only
- Production uses PostgreSQL with full JSONB support

**Temp Directory Management:**
- `test_dirs` session fixture in `conftest.py` creates isolated OUTPUT_DIR/UPLOAD_DIR
- Automatically cleaned up after session ends
- Prevents filesystem pollution across parallel test runs

---

*Testing analysis: 2025-02-27*
