# Tasks: LLM Abstraction Layer

**Input**: Design documents from `/specs/001-llm-abstraction/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests are included as best practice for this foundational component, even though not explicitly required.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/haia/`, `tests/` at repository root
- All paths are absolute from repository root

---

## Phase 1: Setup (Shared Infrastructure) ✅

**Purpose**: Project initialization and directory structure

- [X] T001 Create directory structure: `src/haia/llm/`, `src/haia/llm/providers/`, `tests/unit/llm/`, `tests/integration/`
- [X] T002 [P] Add dependencies to pyproject.toml: `pydantic>=2.0`, `httpx>=0.25`, `anthropic>=0.40`, `pytest>=7.0`, `pytest-asyncio>=0.21`
- [X] T003 [P] Create `src/haia/llm/__init__.py` with module docstring (empty for now, will add exports later)
- [X] T004 [P] Create `src/haia/llm/providers/__init__.py` with module docstring

---

## Phase 2: Foundational (Blocking Prerequisites) ✅

**Purpose**: Core data models and abstractions that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 [P] Implement Pydantic models in `src/haia/llm/models.py`: `Message`, `TokenUsage`, `LLMResponse`, `LLMResponseChunk`
- [X] T006 [P] Implement error hierarchy in `src/haia/llm/errors.py`: `LLMError` base class, `AuthenticationError`, `RateLimitError`, `TimeoutError`, `ValidationError`, `ServiceUnavailableError`, `ResourceNotFoundError`, `InvalidRequestError`
- [X] T007 [P] Implement correlation ID context variable in `src/haia/llm/errors.py` using `contextvars.ContextVar`
- [X] T008 Implement abstract `LLMClient` base class in `src/haia/llm/client.py` with `chat()` and `stream_chat()` methods
- [X] T009 [P] Write unit tests for Pydantic models in `tests/unit/llm/test_models.py`: test validation rules, field constraints, serialization
- [X] T010 [P] Write unit tests for error classes in `tests/unit/llm/test_errors.py`: test error hierarchy, correlation IDs, `to_dict()` method

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel ✅

---

## Phase 3: User Story 1 - Initialize Single LLM Provider (Priority: P1) 🎯 MVP ✅

**Goal**: Enable developers to initialize and use Anthropic Claude through a clean interface for basic chat functionality

**Independent Test**: Send a test message to the LLM client and receive a valid response with token usage ✅ PASSED

### Implementation for User Story 1

- [X] T011 [P] [US1] Implement `AnthropicClient` in `src/haia/llm/providers/anthropic.py`: AsyncAnthropic initialization, `chat()` method, error mapping from Anthropic SDK to unified errors
- [X] T012 [P] [US1] Implement response mapping in `AnthropicClient`: convert Anthropic response to `LLMResponse` model, extract token usage, handle system prompts as top-level parameter
- [X] T013 [P] [US1] Implement stub `stream_chat()` method in `AnthropicClient`: raise `NotImplementedError` with message "Streaming not implemented in MVP"
- [X] T014 [US1] Implement factory function in `src/haia/llm/factory.py`: `create_client(config: Settings) -> LLMClient` supporting "anthropic:model" format
- [X] T015 [US1] Add structured logging to `AnthropicClient`: log all LLM API calls with correlation ID, provider, model, latency, token usage
- [X] T016 [US1] Update `src/haia/llm/__init__.py` to export: `LLMClient`, `create_client`, `Message`, `LLMResponse`, `TokenUsage`, all error types
- [X] T017 [US1] Update `src/haia/llm/providers/__init__.py` to export `AnthropicClient`

### Tests for User Story 1

- [X] T018 [P] [US1] Write unit tests for `AnthropicClient` in `tests/unit/llm/test_anthropic.py`: mock Anthropic API, test successful chat, test error mapping, test response conversion
- [X] T019 [P] [US1] Write unit tests for factory in `tests/unit/llm/test_factory.py`: test Anthropic provider selection, test invalid provider format error, test unsupported provider error
- [X] T020 [US1] Write integration test in `tests/integration/test_llm_providers.py`: test real Anthropic API call (requires API key, marked with `pytest.mark.integration`)

**Checkpoint**: At this point, User Story 1 should be fully functional - can initialize Anthropic client, send messages, receive responses, get token usage ✅ COMPLETE

---

## Phase 4: User Story 2 - Switch LLM Providers via Configuration (Priority: P2)

**Goal**: Enable system administrators to switch between LLM providers by changing HAIA_MODEL configuration value

**Independent Test**: Change HAIA_MODEL config and verify system initializes correct provider and generates responses in identical format

### Implementation for User Story 2

- [ ] T021 [P] [US2] Implement `OllamaClient` in `src/haia/llm/providers/ollama.py`: httpx async client initialization, POST to `/api/chat` endpoint, error mapping from HTTP status codes
- [ ] T022 [P] [US2] Implement response mapping in `OllamaClient`: convert Ollama JSON to `LLMResponse` model, map `prompt_eval_count`/`eval_count` to token usage, handle system prompts as messages with role="system"
- [ ] T023 [P] [US2] Implement stub `stream_chat()` method in `OllamaClient`: raise `NotImplementedError`
- [ ] T024 [US2] Enhance factory function in `src/haia/llm/factory.py`: add "ollama:model" support, validate OLLAMA_BASE_URL config
- [ ] T025 [US2] Update `src/haia/llm/providers/__init__.py` to export `OllamaClient`

### Tests for User Story 2

- [ ] T026 [P] [US2] Write unit tests for `OllamaClient` in `tests/unit/llm/test_ollama.py`: mock httpx responses, test successful chat, test error mapping, test response conversion
- [ ] T027 [P] [US2] Write factory tests for Ollama in `tests/unit/llm/test_factory.py`: test Ollama provider selection, test base_url configuration
- [ ] T028 [US2] Write integration test in `tests/integration/test_llm_providers.py`: test provider switching (initialize both Anthropic and Ollama with same messages, verify identical response format)

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently - can switch providers via config, responses have identical format

---

## Phase 5: User Story 3 - Handle LLM Provider Errors Gracefully (Priority: P2)

**Goal**: Provide informative error messages when LLM providers fail, enabling users to diagnose and resolve issues

**Independent Test**: Simulate various failure scenarios and verify appropriate error responses with debugging information

### Implementation for User Story 3

**Note**: Error handling is largely implemented in US1 and US2. This phase validates and enhances error coverage.

- [ ] T029 [P] [US3] Add timeout configuration to `AnthropicClient`: accept timeout parameter, configure Anthropic SDK timeout
- [ ] T030 [P] [US3] Add timeout configuration to `OllamaClient`: configure httpx client timeout
- [ ] T031 [P] [US3] Enhance error logging in both clients: ensure all error types include provider, error_type, correlation_id, original_error
- [ ] T032 [US3] Add response validation in both clients: validate response against expected Pydantic schema, raise `ValidationError` if malformed

### Tests for User Story 3

- [ ] T033 [P] [US3] Write error scenario tests in `tests/unit/llm/test_anthropic.py`: test AuthenticationError (401), RateLimitError (429), TimeoutError, ValidationError (malformed response)
- [ ] T034 [P] [US3] Write error scenario tests in `tests/unit/llm/test_ollama.py`: test 404 (model not found), 500 (service error), timeout, malformed JSON
- [ ] T035 [US3] Write comprehensive error tests in `tests/unit/llm/test_errors.py`: test correlation ID propagation, test error serialization (`to_dict()`), test exception chaining (`raise ... from e`)

**Checkpoint**: All error scenarios are handled gracefully with informative messages and debugging information

---

## Phase 6: User Story 4 - Support Streaming Responses (Interface Level) (Priority: P3)

**Goal**: Define streaming interface to avoid breaking changes when streaming is implemented post-MVP

**Independent Test**: Call streaming method and verify it's defined in interface (even though it raises NotImplementedError in MVP)

### Implementation for User Story 4

- [ ] T036 [P] [US4] Verify `stream_chat()` abstract method in `src/haia/llm/client.py`: ensure signature includes `AsyncIterator[LLMResponseChunk]` return type
- [ ] T037 [P] [US4] Verify `LLMResponseChunk` model in `src/haia/llm/models.py`: ensure fields for incremental content, finish_reason, usage
- [ ] T038 [P] [US4] Document streaming interface in `src/haia/llm/client.py` docstrings: explain MVP limitation, describe expected behavior when implemented
- [ ] T039 [US4] Add example of future streaming usage to quickstart.md (in code comments showing it's not implemented yet)

### Tests for User Story 4

- [ ] T040 [P] [US4] Write interface test in `tests/unit/llm/test_client.py`: verify `stream_chat()` method exists on abstract class, verify correct return type annotation
- [ ] T041 [US4] Write stub tests for streaming in provider tests: call `stream_chat()`, verify `NotImplementedError` is raised with appropriate message

**Checkpoint**: Streaming interface is defined and documented, ready for post-MVP implementation

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Final improvements, documentation, and validation

- [ ] T042 [P] Run `mypy --strict src/haia/llm/` and fix any type errors
- [ ] T043 [P] Run `ruff check src/haia/llm/` and fix any linting issues
- [ ] T044 [P] Run `ruff format src/haia/llm/` to ensure consistent code style
- [ ] T045 [P] Add comprehensive docstrings to all public classes and methods in `src/haia/llm/`
- [ ] T046 Validate quickstart.md examples: run example code snippets to ensure they work
- [ ] T047 [P] Update README.md with LLM abstraction layer usage if needed
- [ ] T048 Run full test suite: `pytest tests/unit/llm/ -v` and ensure all tests pass
- [ ] T049 Write performance test: measure abstraction layer overhead (<10ms target)
- [ ] T050 Write concurrency test: verify multiple simultaneous LLM calls work without conflicts

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-6)**: All depend on Foundational phase completion
  - User stories can proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P2 → P3)
- **Polish (Phase 7)**: Depends on all user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Independent of US1 (but factory enhancement builds on T014)
- **User Story 3 (P2)**: Depends on US1 and US2 implementation - Validates error handling across both providers
- **User Story 4 (P3)**: Can start after Foundational (Phase 2) - Independent, just interface definition

### Within Each User Story

- Implementation tasks before tests (tests verify implementation)
- Models/abstractions before concrete implementations
- Core functionality before logging/observability enhancements
- Unit tests before integration tests

### Parallel Opportunities

**Setup (Phase 1)**: T002, T003, T004 can run in parallel

**Foundational (Phase 2)**: T005, T006, T007, T009, T010 can run in parallel (T008 depends on T005, T006)

**User Story 1**: T011, T012, T013, T018, T019 can run in parallel (T014-T017 depend on T011-T013; T020 depends on all implementation)

**User Story 2**: T021, T022, T023, T026, T027 can run in parallel (T024-T025 depend on T021-T023; T028 depends on all implementation)

**User Story 3**: T029, T030, T031, T033, T034 can run in parallel (T032 depends on T029-T031; T035 is independent)

**User Story 4**: T036, T037, T038, T040, T041 can run in parallel

**Polish**: T042, T043, T044, T045, T047 can run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch implementation tasks in parallel:
Task: "Implement AnthropicClient in src/haia/llm/providers/anthropic.py"
Task: "Implement response mapping in AnthropicClient"
Task: "Implement stub stream_chat() in AnthropicClient"
Task: "Write unit tests for AnthropicClient in tests/unit/llm/test_anthropic.py"
Task: "Write unit tests for factory in tests/unit/llm/test_factory.py"

# Then run sequential tasks:
Task: "Implement factory function in src/haia/llm/factory.py"
Task: "Add structured logging to AnthropicClient"
Task: "Update exports in src/haia/llm/__init__.py"
Task: "Update exports in src/haia/llm/providers/__init__.py"
Task: "Write integration test in tests/integration/test_llm_providers.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup → Project structure ready
2. Complete Phase 2: Foundational → Core models and abstractions ready
3. Complete Phase 3: User Story 1 → Anthropic client functional
4. **STOP and VALIDATE**: Test US1 independently with real API calls
5. Deploy/integrate with chat API

**MVP Deliverables**:
- Can initialize Anthropic client
- Can send chat messages
- Can receive responses with token usage
- Errors are handled gracefully
- Full type safety (mypy strict passes)

### Incremental Delivery

1. **Setup + Foundational** → Foundation ready
2. **Add User Story 1** → Test independently → **MVP COMPLETE** 🎯
3. **Add User Story 2** → Test independently → Multi-provider support ready
4. **Add User Story 3** → Test independently → Production-ready error handling
5. **Add User Story 4** → Test independently → Future-proof for streaming
6. **Polish** → Production-ready

Each story adds value without breaking previous stories.

### Parallel Team Strategy

With multiple developers:

1. **Everyone**: Complete Setup + Foundational together
2. **Once Foundational is done**:
   - Developer A: User Story 1 (Anthropic implementation)
   - Developer B: User Story 2 (Ollama implementation)
   - Developer C: User Story 3 (Error handling tests)
   - Developer D: User Story 4 (Streaming interface)
3. Stories complete and integrate independently

---

## Task Summary

**Total Tasks**: 50

### Tasks by Phase
- **Phase 1 (Setup)**: 4 tasks
- **Phase 2 (Foundational)**: 6 tasks
- **Phase 3 (US1 - MVP)**: 10 tasks
- **Phase 4 (US2)**: 8 tasks
- **Phase 5 (US3)**: 7 tasks
- **Phase 6 (US4)**: 6 tasks
- **Phase 7 (Polish)**: 9 tasks

### Tasks by User Story
- **US1 (Initialize Single LLM Provider)**: 10 tasks
- **US2 (Switch LLM Providers)**: 8 tasks
- **US3 (Error Handling)**: 7 tasks
- **US4 (Streaming Interface)**: 6 tasks

### Parallelizable Tasks
- **28 tasks marked [P]** can run in parallel within their phase

### MVP Scope (US1 Only)
- **Setup + Foundational + US1 = 20 tasks** for functional MVP

---

## Independent Test Criteria

### User Story 1 Test
```python
# File: tests/integration/test_us1_mvp.py
from haia.llm import create_client, Message
from haia.config import settings

async def test_us1_independent():
    """Test US1: Initialize single LLM provider"""
    client = create_client(settings)  # Should create AnthropicClient

    messages = [Message(role="user", content="Say hello")]
    response = await client.chat(messages=messages)

    assert response.content  # Got content
    assert response.usage.total_tokens > 0  # Got token usage
    assert "anthropic" in response.model.lower()  # Correct provider
```

### User Story 2 Test
```python
# File: tests/integration/test_us2_switching.py
async def test_us2_independent():
    """Test US2: Switch providers via config"""
    # Test with Anthropic
    settings.haia_model = "anthropic:claude-haiku-4-5-20251001"
    client1 = create_client(settings)
    response1 = await client1.chat(messages=[Message(role="user", content="Hi")])

    # Test with Ollama
    settings.haia_model = "ollama:qwen2.5-coder"
    client2 = create_client(settings)
    response2 = await client2.chat(messages=[Message(role="user", content="Hi")])

    # Verify same response format
    assert type(response1) == type(response2)  # Same LLMResponse type
    assert hasattr(response1, 'content') and hasattr(response2, 'content')
```

### User Story 3 Test
```python
# File: tests/unit/llm/test_us3_errors.py
async def test_us3_independent():
    """Test US3: Graceful error handling"""
    from haia.llm import AuthenticationError, create_client

    # Simulate invalid API key
    settings.anthropic_api_key = "invalid"
    client = create_client(settings)

    with pytest.raises(AuthenticationError) as exc_info:
        await client.chat(messages=[Message(role="user", content="Hi")])

    # Verify error has debugging info
    error = exc_info.value
    assert error.provider == "anthropic"
    assert error.correlation_id  # Has correlation ID
    assert error.original_error  # Has original error
```

### User Story 4 Test
```python
# File: tests/unit/llm/test_us4_streaming.py
def test_us4_independent():
    """Test US4: Streaming interface exists"""
    from haia.llm import LLMClient
    import inspect

    # Verify method exists
    assert hasattr(LLMClient, 'stream_chat')

    # Verify return type annotation
    sig = inspect.signature(LLMClient.stream_chat)
    assert 'AsyncIterator' in str(sig.return_annotation)
```

---

## Notes

- [P] tasks = different files, no dependencies within phase
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Run mypy/ruff after each task group to catch issues early
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- MVP = Phase 1 + Phase 2 + Phase 3 (20 tasks total)
