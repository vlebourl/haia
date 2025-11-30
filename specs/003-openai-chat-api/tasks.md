# Tasks: OpenAI-Compatible Chat API with Streaming

**Input**: Design documents from `/specs/003-openai-chat-api/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Tests**: Test tasks are included and should be implemented following TDD approach (test-first development).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3, US4, US5)
- Include exact file paths in descriptions

## Path Conventions

- Single project structure: `src/haia/` for source, `tests/` for tests
- API module: `src/haia/api/` (new for this feature)
- Existing modules: `src/haia/llm/` (Feature 001), `src/haia/db/` (Feature 002)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and dependency installation

- [X] T001 Add FastAPI dependencies to pyproject.toml (fastapi, uvicorn, sse-starlette)
- [X] T002 [P] Add PydanticAI dependency to pyproject.toml (pydantic-ai)
- [X] T003 [P] Install all dependencies via uv sync
- [X] T004 Create src/haia/api/ directory structure (routes/, models/, __init__.py, app.py, deps.py)
- [X] T005 [P] Create tests/unit/api/ directory structure
- [X] T006 [P] Create tests/integration/api/ directory structure
- [X] T007 [P] Create tests/contract/ directory for OpenAPI validation

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T008 Create ChatMessage model in src/haia/api/models/chat.py (base for all request/response)
- [X] T009 [P] Create ErrorDetail and ErrorResponse models in src/haia/api/models/errors.py
- [X] T010 [P] Create TokenUsage model in src/haia/api/models/chat.py
- [X] T011 Create system prompt constant in src/haia/agent.py (HOMELAB_ASSISTANT_PROMPT)
- [X] T012 Implement create_agent() function in src/haia/agent.py (PydanticAI agent initialization)
- [X] T013 Implement get_agent() dependency in src/haia/api/deps.py (global agent instance)
- [X] T014 [P] Implement correlation ID context var in src/haia/api/deps.py (ContextVar setup)
- [X] T015 [P] Implement get_correlation_id() dependency in src/haia/api/deps.py
- [X] T016 Create FastAPI app instance in src/haia/api/app.py with startup/shutdown handlers
- [X] T017 Configure CORS middleware in src/haia/api/app.py
- [X] T018 Create main.py entry point in src/haia/main.py for uvicorn launcher
- [X] T019 [P] Write unit tests for agent initialization in tests/unit/api/test_agent.py
- [X] T020 [P] Write unit tests for dependency injection in tests/unit/api/test_deps.py

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Basic Chat Interaction (Priority: P1) 🎯 MVP

**Goal**: Implement non-streaming chat endpoint with agent integration and basic conversation persistence

**Independent Test**: Send POST to `/v1/chat/completions` with `stream: false`, receive complete JSON response with assistant message

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T021 [P] [US1] Contract test for /v1/chat/completions non-streaming in tests/contract/test_openai_compatibility.py
- [X] T022 [P] [US1] Integration test for basic chat flow in tests/integration/api/test_chat_flow.py
- [X] T023 [P] [US1] Unit test for ChatCompletionRequest validation in tests/unit/api/test_models.py

### Implementation for User Story 1

- [X] T024 [P] [US1] Create ChatCompletionRequest model in src/haia/api/models/chat.py (with validation)
- [X] T025 [P] [US1] Create Choice model in src/haia/api/models/chat.py
- [X] T026 [P] [US1] Create ChatCompletionResponse model with factory method in src/haia/api/models/chat.py
- [X] T027 [US1] Create /v1/chat/completions POST endpoint in src/haia/api/routes/chat.py (non-streaming only)
- [X] T028 [US1] Implement chat_completions() handler function with agent.run() integration
- [X] T029 [US1] Add request validation and error handling to chat endpoint
- [X] T030 [US1] Implement conversation creation in chat handler (use ConversationRepository)
- [X] T031 [US1] Implement user message saving to database in chat handler
- [X] T032 [US1] Implement assistant response saving to database in chat handler
- [X] T033 [US1] Add correlation ID logging to chat requests
- [X] T034 [US1] Register chat router in src/haia/api/app.py

**Checkpoint**: At this point, User Story 1 should be fully functional - can send chat request, get response, conversation persisted

---

## Phase 4: User Story 2 - Real-Time Streaming Responses (Priority: P1)

**Goal**: Add Server-Sent Events (SSE) streaming support for real-time token delivery

**Independent Test**: Send POST to `/v1/chat/completions` with `stream: true`, receive SSE event stream with progressive chunks

### Tests for User Story 2

- [X] T035 [P] [US2] Integration test for SSE streaming in tests/integration/api/test_streaming.py
- [X] T036 [P] [US2] Test client disconnection handling in tests/integration/api/test_streaming.py
- [X] T037 [P] [US2] Unit test for streaming chunk models in tests/unit/api/test_models.py

### Implementation for User Story 2

- [X] T038 [P] [US2] Create MessageDelta model in src/haia/api/models/chat.py
- [X] T039 [P] [US2] Create ChoiceDelta model in src/haia/api/models/chat.py
- [X] T040 [P] [US2] Create ChatCompletionChunk model with factory methods in src/haia/api/models/chat.py
- [X] T041 [US2] Implement stream_chat_response() async generator in src/haia/api/routes/chat.py
- [X] T042 [US2] Add SSE response handling to chat_completions() endpoint (check request.stream)
- [X] T043 [US2] Implement chunk collection for database save in stream generator
- [X] T044 [US2] Add final chunk with usage stats and finish_reason to stream
- [X] T045 [US2] Implement graceful disconnection handling in stream generator
- [X] T046 [US2] Add SSE event formatting (data: prefix, [DONE] terminator)

**Checkpoint**: At this point, both non-streaming and streaming modes work - User Stories 1 AND 2 are functional

---

## Phase 5: User Story 3 - Persistent Conversation History (Priority: P1)

**Goal**: Load conversation history from database and maintain 20-message context window

**Independent Test**: Send multiple messages to same conversation, verify agent maintains context and only loads 20 most recent messages

### Tests for User Story 3

- [ ] T047 [P] [US3] Integration test for conversation persistence in tests/integration/api/test_persistence.py
- [ ] T048 [P] [US3] Integration test for 20-message context window in tests/integration/api/test_persistence.py
- [ ] T049 [P] [US3] Test conversation ID handling in tests/integration/api/test_persistence.py

### Implementation for User Story 3

- [ ] T050 [US3] Implement conversation ID extraction from request in chat_completions()
- [ ] T051 [US3] Add conversation existence check (get_conversation or create new)
- [ ] T052 [US3] Implement context history loading using get_context_messages() from repository
- [ ] T053 [US3] Convert database messages to ChatMessage format for agent
- [ ] T054 [US3] Pass conversation context to agent.run() as message history
- [ ] T055 [US3] Update conversation.updated_at after each message
- [ ] T056 [US3] Add logging for context window size (debug level)

**Checkpoint**: Conversations now persist across requests with proper context window - All P1 stories (US1, US2, US3) are complete

---

## Phase 6: User Story 4 - Error Handling and Resilience (Priority: P2)

**Goal**: Comprehensive error handling with appropriate HTTP status codes and graceful degradation

**Independent Test**: Simulate various failures (disconnected Ollama, invalid request, database error), verify appropriate error responses returned

### Tests for User Story 4

- [ ] T057 [P] [US4] Integration test for LLM provider errors in tests/integration/api/test_error_handling.py
- [ ] T058 [P] [US4] Integration test for database errors in tests/integration/api/test_error_handling.py
- [ ] T059 [P] [US4] Integration test for validation errors in tests/integration/api/test_error_handling.py

### Implementation for User Story 4

- [ ] T060 [P] [US4] Create error response helper functions in src/haia/api/models/errors.py
- [ ] T061 [US4] Implement LLM error handling in chat_completions() (map LLMError to HTTP status)
- [ ] T062 [US4] Add AuthenticationError → 401 mapping
- [ ] T063 [US4] Add RateLimitError → 429 mapping with Retry-After header
- [ ] T064 [US4] Add TimeoutError → 504 mapping
- [ ] T065 [US4] Add ServiceUnavailableError → 503 mapping
- [ ] T066 [US4] Implement database error handling (catch and return 500)
- [ ] T067 [US4] Add validation error handling (Pydantic ValidationError → 400)
- [ ] T068 [US4] Implement streaming error handling (send error event, close stream)
- [ ] T069 [US4] Add correlation ID to all error log entries
- [ ] T070 [US4] Test error responses don't leak sensitive information (stack traces, etc.)

**Checkpoint**: Error handling is production-ready - all error scenarios have graceful responses

---

## Phase 7: User Story 5 - Model Selection and Configuration (Priority: P3)

**Goal**: Validate configuration and support switching between Anthropic and Ollama providers

**Independent Test**: Change HAIA_MODEL environment variable, restart server, verify new model is used

### Tests for User Story 5

- [ ] T071 [P] [US5] Integration test for Anthropic provider in tests/integration/api/test_providers.py
- [ ] T072 [P] [US5] Integration test for Ollama provider in tests/integration/api/test_providers.py
- [ ] T073 [P] [US5] Test invalid model configuration handling in tests/integration/api/test_providers.py

### Implementation for User Story 5

- [ ] T074 [US5] Add model configuration validation to startup handler in src/haia/api/app.py
- [ ] T075 [US5] Implement fail-fast behavior for invalid HAIA_MODEL (raise clear error)
- [ ] T076 [US5] Add model name to response (echo from request or use config)
- [ ] T077 [US5] Test provider switching in startup handler
- [ ] T078 [US5] Add logging for active model/provider on startup

**Checkpoint**: All user stories (US1-US5) are complete and independently testable

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final touches that affect multiple user stories

- [ ] T079 [P] Create health check endpoint in src/haia/api/routes/health.py
- [ ] T080 [P] Register health router in src/haia/api/app.py
- [ ] T081 [P] Add structured logging configuration in src/haia/api/app.py
- [ ] T082 [P] Implement CorrelationIdFilter for logging in src/haia/api/deps.py
- [ ] T083 [P] Add database initialization to startup handler (call init_db)
- [ ] T084 [P] Add shutdown handler for cleanup (close_db)
- [ ] T085 [P] Update CORS_ORIGINS configuration in src/haia/config.py
- [ ] T086 [P] Add API server host/port configuration to src/haia/config.py
- [ ] T087 [P] Write contract test for health endpoint in tests/contract/test_openai_compatibility.py
- [ ] T088 [P] Write unit tests for error models in tests/unit/api/test_errors.py
- [ ] T089 [P] Write unit tests for Pydantic models validation in tests/unit/api/test_models.py
- [ ] T090 Run mypy --strict on src/haia/api/ and fix any type errors
- [ ] T091 Run ruff check on src/haia/api/ and fix any linting issues
- [ ] T092 Run ruff format on src/haia/api/ for consistent code style
- [ ] T093 Run all tests and ensure 100% pass rate (uv run pytest -v)
- [ ] T094 Validate quickstart.md instructions work end-to-end
- [ ] T095 [P] Add inline documentation (docstrings) for all public functions
- [ ] T096 Test OpenWebUI integration manually (configure and send test messages)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-7)**: All depend on Foundational phase completion
  - User Story 1 (US1): Can start after Foundational - No dependencies on other stories
  - User Story 2 (US2): Can start after Foundational - Extends US1 but independently testable
  - User Story 3 (US3): Can start after Foundational - Extends US1 but independently testable
  - User Story 4 (US4): Can start after Foundational - Enhances all stories but independently testable
  - User Story 5 (US5): Can start after Foundational - Configuration layer, independently testable
- **Polish (Phase 8)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Foundation for chat functionality - RECOMMENDED for MVP
- **User Story 2 (P1)**: Adds streaming to US1 - Can start after US1 complete or in parallel
- **User Story 3 (P1)**: Adds persistence to US1 - Can start after US1 complete or in parallel
- **User Story 4 (P2)**: Error handling for all stories - Can start after any story is complete
- **User Story 5 (P3)**: Configuration validation - Can start after Foundational phase

**Note**: While some stories extend US1, they should remain independently testable. For example, US2 (streaming) can be tested by checking SSE stream behavior without relying on US3 (persistence).

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services/handlers
- Core implementation before integration
- Logging and validation after core functionality
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1: Setup**
- T002 [P], T005 [P], T006 [P], T007 [P] can all run in parallel

**Phase 2: Foundational**
- T009 [P], T010 [P], T014 [P], T015 [P], T019 [P], T020 [P] can run in parallel

**User Story 1: Tests**
- T021 [P], T022 [P], T023 [P] can run in parallel

**User Story 1: Models**
- T024 [P], T025 [P], T026 [P] can run in parallel (different models, no dependencies)

**User Story 2: Models**
- T038 [P], T039 [P], T040 [P] can run in parallel

**User Story 2: Tests**
- T035 [P], T036 [P], T037 [P] can run in parallel

**User Story 3: Tests**
- T047 [P], T048 [P], T049 [P] can run in parallel

**User Story 4: Tests**
- T057 [P], T058 [P], T059 [P] can run in parallel

**User Story 4: Error Mappings**
- T060 [P] can run standalone

**User Story 5: Tests**
- T071 [P], T072 [P], T073 [P] can run in parallel

**Phase 8: Polish**
- T079 [P], T080 [P], T081 [P], T082 [P], T083 [P], T084 [P], T085 [P], T086 [P], T087 [P], T088 [P], T089 [P], T095 [P] can run in parallel

**Different User Stories**
- Once Foundational phase completes, ALL user stories (US1-US5) can be worked on in parallel by different team members

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task T021: "Contract test for /v1/chat/completions non-streaming in tests/contract/test_openai_compatibility.py"
Task T022: "Integration test for basic chat flow in tests/integration/api/test_chat_flow.py"
Task T023: "Unit test for ChatCompletionRequest validation in tests/unit/api/test_models.py"

# Launch all models for User Story 1 together:
Task T024: "Create ChatCompletionRequest model in src/haia/api/models/chat.py"
Task T025: "Create Choice model in src/haia/api/models/chat.py"
Task T026: "Create ChatCompletionResponse model with factory method in src/haia/api/models/chat.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T007)
2. Complete Phase 2: Foundational (T008-T020) - CRITICAL
3. Complete Phase 3: User Story 1 (T021-T034)
4. **STOP and VALIDATE**: Test User Story 1 independently
   - Send POST to /v1/chat/completions
   - Verify response is correct
   - Verify conversation persisted to database
5. Deploy/demo if ready

**MVP Checkpoint**: At task T034, you have a working chat API with non-streaming responses and basic persistence.

### Incremental Delivery

1. **Foundation** (T001-T020) → Core infrastructure ready
2. **MVP** (T021-T034) → User Story 1 → Basic chat works → Deploy/Demo
3. **Streaming** (T035-T046) → User Story 2 → Real-time responses → Deploy/Demo
4. **Persistence** (T047-T056) → User Story 3 → Full context → Deploy/Demo
5. **Robustness** (T057-T070) → User Story 4 → Production-ready → Deploy/Demo
6. **Flexibility** (T071-T078) → User Story 5 → Multi-provider → Deploy/Demo
7. **Polish** (T079-T096) → Final quality pass → Production release

Each increment adds value without breaking previous functionality.

### Parallel Team Strategy

With multiple developers:

1. **Team completes Setup + Foundational together** (T001-T020)
2. Once Foundational is done (after T020):
   - Developer A: User Story 1 (T021-T034) - MVP focus
   - Developer B: User Story 2 (T035-T046) - Streaming
   - Developer C: User Story 3 (T047-T056) - Context persistence
3. After P1 stories complete:
   - Developer D: User Story 4 (T057-T070) - Error handling
   - Developer E: User Story 5 (T071-T078) - Configuration
4. All developers: Polish phase (T079-T096) - parallel polish tasks

---

## Task Summary

**Total Tasks**: 96

**By Phase**:
- Phase 1 (Setup): 7 tasks
- Phase 2 (Foundational): 13 tasks (BLOCKING)
- Phase 3 (US1 - Basic Chat): 14 tasks (MVP)
- Phase 4 (US2 - Streaming): 12 tasks
- Phase 5 (US3 - Persistence): 10 tasks
- Phase 6 (US4 - Error Handling): 14 tasks
- Phase 7 (US5 - Configuration): 8 tasks
- Phase 8 (Polish): 18 tasks

**By Priority**:
- P1 Stories (US1, US2, US3): 36 implementation tasks
- P2 Stories (US4): 14 tasks
- P3 Stories (US5): 8 tasks
- Setup + Foundational: 20 tasks
- Polish: 18 tasks

**Parallel Opportunities**: 41 tasks marked [P] can run in parallel

**MVP Scope**: Tasks T001-T034 (41 tasks total) delivers a working chat API

**Independent Test Criteria**:
- US1: POST /v1/chat/completions returns JSON response
- US2: POST /v1/chat/completions with stream=true returns SSE chunks
- US3: Multiple messages maintain conversation context
- US4: Error scenarios return appropriate HTTP status codes
- US5: Server starts with different HAIA_MODEL values

---

## Notes

- [P] tasks = different files, no dependencies within same phase
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Write tests FIRST, ensure they FAIL before implementing
- Commit after each task or logical group of related tasks
- Stop at any checkpoint to validate story independently
- Run type checking (mypy), linting (ruff), formatting (ruff) after each phase
- Validate against quickstart.md scenarios throughout development
