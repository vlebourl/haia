# Tasks: Conversation Database Persistence

**Input**: Design documents from `/specs/002-conversation-db/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/repository.json, quickstart.md

**Tests**: Included - unit tests for repository methods and integration tests with real SQLite database

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Single project**: `src/haia/`, `tests/` at repository root
- Database layer: `src/haia/db/`
- Tests: `tests/unit/db/` and `tests/integration/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create database module directory structure (src/haia/db/ with __init__.py)
- [X] T002 Add database dependencies to pyproject.toml (sqlalchemy[asyncio]>=2.0, aiosqlite>=0.17, alembic>=1.12)
- [X] T003 [P] Initialize Alembic in src/haia/db/migrations/ directory
- [X] T004 [P] Configure Alembic alembic.ini with SQLite async URL
- [X] T005 [P] Update Alembic env.py for async migrations support

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core database infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 Create Base declarative model class in src/haia/db/models.py
- [X] T007 Setup async database engine creation in src/haia/db/session.py
- [X] T008 Create async_sessionmaker factory in src/haia/db/session.py
- [X] T009 Implement get_db() FastAPI dependency function in src/haia/db/session.py
- [X] T010 Create ConversationRepository class skeleton in src/haia/db/repository.py
- [X] T011 Export public API from src/haia/db/__init__.py (get_db, Base, Repository)
- [X] T012 Add DATABASE_URL to src/haia/config.py Settings class

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Persist Conversation Messages (Priority: P1) 🎯 MVP

**Goal**: Enable automatic persistence of conversation messages with full retrieval capability across application restarts

**Independent Test**: Create conversation, add messages, restart application, retrieve conversation and verify all messages are intact with correct content, roles, and timestamps in chronological order

### Tests for User Story 1

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T013 [P] [US1] Create test_models.py with Conversation model validation tests in tests/unit/db/
- [X] T014 [P] [US1] Create test_models.py with Message model validation tests in tests/unit/db/
- [X] T015 [P] [US1] Create test_repository.py with create_conversation unit tests in tests/unit/db/
- [X] T016 [P] [US1] Create test_repository.py with add_message unit tests in tests/unit/db/
- [X] T017 [P] [US1] Create test_repository.py with get_conversation unit tests in tests/unit/db/
- [X] T018 [P] [US1] Create test_db_persistence.py with integration test for message persistence in tests/integration/

### Implementation for User Story 1

- [X] T019 [P] [US1] Create Conversation model with id, created_at, updated_at fields in src/haia/db/models.py
- [X] T020 [P] [US1] Create Message model with id, conversation_id, role, content, created_at in src/haia/db/models.py
- [X] T021 [US1] Add relationship mapping between Conversation and Message models in src/haia/db/models.py
- [X] T022 [US1] Add indexes on Conversation (created_at, updated_at) in src/haia/db/models.py
- [X] T023 [US1] Add indexes on Message (conversation_id, created_at) in src/haia/db/models.py
- [X] T024 [US1] Add composite index on Message (conversation_id, created_at) in src/haia/db/models.py
- [X] T025 [P] [US1] Implement create_conversation() method in src/haia/db/repository.py
- [X] T026 [P] [US1] Implement get_conversation() method in src/haia/db/repository.py
- [X] T027 [P] [US1] Implement add_message() method in src/haia/db/repository.py
- [X] T028 [P] [US1] Implement get_all_messages() method in src/haia/db/repository.py
- [X] T029 [US1] Add role validation in add_message() method (system/user/assistant)
- [X] T030 [US1] Add error handling for missing conversation_id in add_message()
- [X] T031 [US1] Generate initial Alembic migration (001_initial_schema.py) for Conversation and Message tables
- [X] T032 [US1] Add logging for conversation creation and message persistence operations
- [X] T033 [US1] Run unit tests and verify all US1 tests pass
- [X] T034 [US1] Run integration tests and verify message persistence across restarts

**Checkpoint**: At this point, User Story 1 should be fully functional - conversations can be created, messages persisted, and retrieved after application restart

---

## Phase 4: User Story 2 - Automatic Context Window Management (Priority: P2)

**Goal**: Automatically maintain a 20-message context window for LLM processing while preserving full conversation history

**Independent Test**: Create conversation with 30 messages, retrieve context window and verify exactly 20 most recent messages returned in chronological order, verify all 30 messages still in database

### Tests for User Story 2

- [X] T035 [P] [US2] Create test_repository.py with get_context_messages unit tests in tests/unit/db/
- [X] T036 [P] [US2] Create test_context_window.py integration test for 20-message limit in tests/integration/
- [X] T037 [P] [US2] Create test_context_window.py integration test for conversations under 20 messages in tests/integration/

### Implementation for User Story 2

- [X] T038 [US2] Implement get_context_messages() method with ORDER BY and LIMIT in src/haia/db/repository.py
- [X] T039 [US2] Add query optimization using composite index (conversation_id, created_at) in get_context_messages()
- [X] T040 [US2] Add message reversal logic to return chronological order (oldest first) in get_context_messages()
- [X] T041 [US2] Add configurable limit parameter (default=20) to get_context_messages() method
- [X] T042 [US2] Add logging for context window retrieval operations
- [X] T043 [US2] Run unit tests and verify context window logic correctness
- [X] T044 [US2] Run integration tests with conversations >20 and <20 messages
- [X] T045 [US2] Performance test: Verify context retrieval <20ms for 1000-message conversation

**Checkpoint**: At this point, User Stories 1 AND 2 should both work - full message persistence with efficient context window queries

---

## Phase 5: User Story 3 - Conversation Metadata and Organization (Priority: P3)

**Goal**: Track conversation metadata (creation time, last update) and enable conversation listing and management

**Independent Test**: Create multiple conversations with messages, list conversations and verify sorted by last update time with metadata, verify message count accurate, delete conversation and verify cascade deletion

### Tests for User Story 3

- [X] T046 [P] [US3] Create test_repository.py with list_conversations unit tests in tests/unit/db/
- [X] T047 [P] [US3] Create test_repository.py with delete_conversation unit tests in tests/unit/db/
- [X] T048 [P] [US3] Create test_repository.py with get_message_count unit tests in tests/unit/db/
- [X] T049 [P] [US3] Create test_conversation_management.py integration test for listing in tests/integration/
- [X] T050 [P] [US3] Create test_conversation_management.py integration test for cascade delete in tests/integration/

### Implementation for User Story 3

- [X] T051 [P] [US3] Implement list_conversations() method with ORDER BY updated_at DESC in src/haia/db/repository.py
- [X] T052 [P] [US3] Implement delete_conversation() method with CASCADE behavior in src/haia/db/repository.py
- [X] T053 [P] [US3] Implement get_message_count() method with COUNT query in src/haia/db/repository.py
- [X] T054 [US3] Add pagination support (limit, offset) to list_conversations() method
- [X] T055 [US3] Add automatic updated_at timestamp update on message addition
- [X] T056 [US3] Verify CASCADE delete constraint in Message foreign key configuration
- [X] T057 [US3] Add logging for conversation listing and deletion operations
- [X] T058 [US3] Run unit tests and verify metadata tracking correctness
- [X] T059 [US3] Run integration tests and verify cascade deletion works
- [X] T060 [US3] Performance test: Verify list_conversations <30ms for 100 conversations

**Checkpoint**: All user stories should now be independently functional - complete conversation lifecycle management with context windows

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T061 [P] Create Pydantic models (MessageCreate, MessageResponse, ConversationResponse) in src/haia/db/models.py
- [X] T062 [P] Add SQLAlchemy event hooks for query logging (DEBUG level) in src/haia/db/session.py
- [X] T063 [P] Document repository usage examples in src/haia/db/repository.py docstrings
- [X] T064 Add connection pooling configuration (pool_size, max_overflow) to engine creation
- [X] T065 Add database initialization function (init_db) for schema creation in src/haia/db/session.py
- [X] T066 Add auto-migration application on startup in src/haia/db/session.py
- [X] T067 [P] Add comprehensive error handling with custom exceptions
- [X] T068 [P] Add unit tests for session lifecycle (get_db dependency) in tests/unit/db/test_session.py
- [X] T069 [P] Add integration test for concurrent writes in tests/integration/test_concurrency.py
- [X] T070 Review and optimize all database queries for performance
- [X] T071 Run full test suite and verify 100% pass rate
- [X] T072 Validate quickstart.md examples work correctly
- [X] T073 Performance benchmark: Verify all success criteria met (<100ms retrieval for 1000 messages)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies - can start immediately
- **Foundational (Phase 2)**: Depends on Setup completion - BLOCKS all user stories
- **User Stories (Phase 3-5)**: All depend on Foundational phase completion
  - User stories can then proceed in parallel (if staffed)
  - Or sequentially in priority order (P1 → P2 → P3)
- **Polish (Phase 6)**: Depends on all desired user stories being complete

### User Story Dependencies

- **User Story 1 (P1)**: Can start after Foundational (Phase 2) - No dependencies on other stories ✅ INDEPENDENT
- **User Story 2 (P2)**: Can start after Foundational (Phase 2) - Builds on US1 repository but independently testable ✅ INDEPENDENT
- **User Story 3 (P3)**: Can start after Foundational (Phase 2) - Builds on US1 repository but independently testable ✅ INDEPENDENT

### Within Each User Story

- Tests MUST be written and FAIL before implementation
- Models before services/repository methods
- Core implementation before performance optimization
- Story complete before moving to next priority

### Parallel Opportunities

**Phase 1 (Setup)**: T003, T004, T005 can run in parallel after T001-T002

**Phase 2 (Foundational)**: All tasks sequential (each builds on previous)

**Phase 3 (User Story 1)**:
- Tests T013-T018 can all run in parallel
- Models T019-T020 can run in parallel
- Repository methods T025-T028 can run in parallel after models complete

**Phase 4 (User Story 2)**:
- Tests T035-T037 can all run in parallel
- Implementation is mostly sequential (query optimization)

**Phase 5 (User Story 3)**:
- Tests T046-T050 can all run in parallel
- Repository methods T051-T053 can run in parallel

**Phase 6 (Polish)**:
- T061, T062, T063, T067, T068, T069 can all run in parallel

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together:
Task: "Create test_models.py with Conversation model validation tests in tests/unit/db/"
Task: "Create test_models.py with Message model validation tests in tests/unit/db/"
Task: "Create test_repository.py with create_conversation unit tests in tests/unit/db/"
Task: "Create test_repository.py with add_message unit tests in tests/unit/db/"
Task: "Create test_repository.py with get_conversation unit tests in tests/unit/db/"
Task: "Create test_db_persistence.py with integration test for message persistence in tests/integration/"

# Launch all models for User Story 1 together:
Task: "Create Conversation model with id, created_at, updated_at fields in src/haia/db/models.py"
Task: "Create Message model with id, conversation_id, role, content, created_at in src/haia/db/models.py"

# Launch all repository methods for User Story 1 together:
Task: "Implement create_conversation() method in src/haia/db/repository.py"
Task: "Implement get_conversation() method in src/haia/db/repository.py"
Task: "Implement add_message() method in src/haia/db/repository.py"
Task: "Implement get_all_messages() method in src/haia/db/repository.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T005) ✅ ~30 minutes
2. Complete Phase 2: Foundational (T006-T012) ✅ CRITICAL - blocks all stories ~1 hour
3. Complete Phase 3: User Story 1 (T013-T034) ✅ MVP ~3 hours
4. **STOP and VALIDATE**: Test User Story 1 independently
5. Deploy/integrate with LLM abstraction layer if ready

**MVP Deliverable**: Conversations persist across restarts, all messages stored and retrievable

### Incremental Delivery

1. Complete Setup + Foundational (T001-T012) → Foundation ready ~1.5 hours
2. Add User Story 1 (T013-T034) → Test independently → Deploy/Demo (MVP!) ~3 hours
3. Add User Story 2 (T035-T045) → Test independently → Deploy/Demo ~1.5 hours
4. Add User Story 3 (T046-T060) → Test independently → Deploy/Demo ~2 hours
5. Polish (T061-T073) → Final hardening ~1.5 hours

**Total Estimated Time**: ~9.5 hours for complete feature

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (T001-T012)
2. Once Foundational is done:
   - Developer A: User Story 1 (T013-T034)
   - Developer B: User Story 2 (T035-T045) - can start immediately after foundational
   - Developer C: User Story 3 (T046-T060) - can start immediately after foundational
3. Stories complete and integrate independently
4. All developers converge on Polish phase (T061-T073)

**Parallel Estimated Time**: ~5 hours with 3 developers

---

## Task Summary

**Total Tasks**: 73

**Breakdown by Phase**:
- Phase 1 (Setup): 5 tasks
- Phase 2 (Foundational): 7 tasks ⚠️ BLOCKING
- Phase 3 (User Story 1 - MVP): 22 tasks (6 test tasks + 16 implementation tasks)
- Phase 4 (User Story 2): 11 tasks (3 test tasks + 8 implementation tasks)
- Phase 5 (User Story 3): 15 tasks (5 test tasks + 10 implementation tasks)
- Phase 6 (Polish): 13 tasks

**Breakdown by User Story**:
- User Story 1 (P1 - MVP): 22 tasks
- User Story 2 (P2): 11 tasks
- User Story 3 (P3): 15 tasks
- Infrastructure (Setup + Foundational + Polish): 25 tasks

**Parallel Opportunities**: 30 tasks marked [P] can run in parallel within their phase

**Independent Test Criteria**:
- ✅ User Story 1: Create/add messages → restart app → retrieve all messages intact
- ✅ User Story 2: Create 30 messages → get context → verify exactly 20 most recent returned
- ✅ User Story 3: Create conversations → list → verify sorted by updated_at, delete → verify cascade

**MVP Scope**: Phase 1 + Phase 2 + Phase 3 (34 tasks total, ~4.5 hours)

---

## Format Validation

✅ All tasks follow checklist format: `- [ ] [ID] [P?] [Story?] Description`
✅ All task IDs sequential (T001-T073)
✅ All user story tasks have [US1], [US2], or [US3] labels
✅ All parallelizable tasks marked with [P]
✅ All implementation tasks include specific file paths
✅ Tests written BEFORE implementation within each user story

---

## Notes

- [P] tasks = different files, no dependencies, can run in parallel
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Write tests first, verify they FAIL before implementing
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- All success criteria from spec.md mapped to tasks (see Phase 6 T073)
