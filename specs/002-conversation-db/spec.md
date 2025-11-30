# Feature Specification: Conversation Database Persistence

**Feature Branch**: `002-conversation-db`
**Created**: 2025-11-30
**Status**: Draft
**Input**: User description: "Database Setup for conversation persistence - SQLite with SQLAlchemy async, store conversations with 20-message context window, single user for MVP"

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Persist Conversation Messages (Priority: P1)

As a user, I need my conversation history to be saved automatically so that I can continue previous conversations after closing and reopening the application, without losing context or having to re-explain my requests.

**Why this priority**: This is the core value proposition of conversation persistence. Without the ability to save and retrieve messages, the chat feature would be stateless and significantly less useful. This is the minimum viable product.

**Independent Test**: Can be fully tested by sending messages in a conversation, restarting the application, and verifying that the conversation history is still available and complete. Delivers immediate value by enabling conversation continuity.

**Acceptance Scenarios**:

1. **Given** a new conversation is started, **When** the user sends a message, **Then** the message is immediately persisted to the database with correct content, role, and timestamp
2. **Given** a conversation with existing messages, **When** the user sends a new message, **Then** the new message is appended to the conversation in chronological order
3. **Given** a conversation with saved messages, **When** the application restarts and the conversation is retrieved, **Then** all messages are returned in the correct order with complete content
4. **Given** multiple conversations exist, **When** a specific conversation is retrieved, **Then** only messages from that conversation are returned

---

### User Story 2 - Automatic Context Window Management (Priority: P2)

As a user, I need the system to automatically maintain a manageable conversation context so that the LLM receives relevant recent messages without being overwhelmed by very long conversation histories, ensuring optimal response quality and performance.

**Why this priority**: Context window management is essential for LLM performance and cost optimization, but the basic conversation persistence (US1) can function without it. This can be implemented and tested independently after US1 is working.

**Independent Test**: Can be tested by creating a conversation with more than 20 messages and verifying that only the 20 most recent messages are included in the context sent to the LLM, while all messages remain stored in the database.

**Acceptance Scenarios**:

1. **Given** a conversation with exactly 20 messages, **When** a new message is added, **Then** all 21 messages are stored in the database but only the 20 most recent are marked for LLM context
2. **Given** a conversation with 30 messages, **When** the context is retrieved for LLM processing, **Then** exactly the 20 most recent messages are returned in chronological order
3. **Given** a conversation with 15 messages, **When** the context is retrieved, **Then** all 15 messages are included (window size not yet reached)
4. **Given** a conversation where old messages exist outside the context window, **When** the conversation is retrieved for display, **Then** all messages are available for viewing but only the context window messages are used for LLM processing

---

### User Story 3 - Conversation Metadata and Organization (Priority: P3)

As a user, I need conversations to have metadata (creation time, last update time) so that I can track conversation history and identify when conversations were started and last modified.

**Why this priority**: Metadata enhances usability and provides valuable information for debugging and organization, but isn't critical for the core conversation persistence functionality. The system can work with just messages in US1 and US2. This can be added later to improve the user experience.

**Independent Test**: Can be tested by creating conversations and verifying that metadata is automatically generated, updated, and retrievable without affecting the core message persistence functionality.

**Acceptance Scenarios**:

1. **Given** a new conversation is created, **When** the first message is sent, **Then** the conversation has a creation timestamp and last update timestamp automatically set
2. **Given** an existing conversation, **When** a new message is added, **Then** the last update timestamp is automatically updated to the current time
3. **Given** a conversation with messages, **When** the conversation metadata is retrieved, **Then** it includes creation time, last update time, and message count
4. **Given** multiple conversations exist, **When** conversations are listed, **Then** they are sorted by last update time with most recent first

---

### Edge Cases

- What happens when the database file doesn't exist on first startup?
  - System automatically creates the database file and initializes schema
- What happens when a database write fails (disk full, permissions error)?
  - System logs the error and returns a clear error message to the user without crashing
- What happens when attempting to retrieve a non-existent conversation?
  - System returns an empty result or appropriate "not found" indicator
- What happens when concurrent requests try to write to the same conversation?
  - Async SQLAlchemy handles concurrency; messages are queued and written sequentially
- What happens when the database schema needs to be updated (migrations)?
  - Migration system automatically detects and applies schema updates on startup

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST persist all conversation messages to a SQLite database file with message content, role (user/assistant/system), and timestamp
- **FR-002**: System MUST retrieve conversation history in chronological order (oldest to newest)
- **FR-003**: System MUST support creating new conversations and appending messages to existing conversations
- **FR-004**: System MUST maintain a 20-message context window where only the 20 most recent messages are used for LLM context
- **FR-005**: System MUST store all messages in the database regardless of context window size (archive for reference/debugging)
- **FR-006**: System MUST use async database operations to avoid blocking the API server
- **FR-007**: System MUST automatically create the database file and schema on first startup if they don't exist
- **FR-008**: System MUST support database schema migrations for future updates
- **FR-009**: System MUST associate all messages with a conversation ID for multi-conversation support (future-proofing)
- **FR-010**: System MUST record conversation metadata including creation time and last update time
- **FR-011**: System MUST handle database errors gracefully without crashing the application
- **FR-012**: System MUST use connection pooling for efficient database access in async context

### Key Entities

- **Conversation**: Represents a conversation thread containing multiple messages
  - Attributes: ID (unique identifier), created_at (timestamp), updated_at (timestamp)
  - Relationships: Has many Messages
  - Note: MVP supports single user, so no user_id field needed initially

- **Message**: Represents a single message in a conversation
  - Attributes: ID (unique identifier), conversation_id (foreign key), role (system/user/assistant), content (text), created_at (timestamp), in_context_window (boolean flag for 20-message window)
  - Relationships: Belongs to one Conversation
  - Note: Messages are ordered chronologically within a conversation

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Messages persist across application restarts with 100% data integrity (no message loss)
- **SC-002**: Conversation retrieval completes in under 100 milliseconds for conversations up to 1000 messages
- **SC-003**: Database writes complete asynchronously without blocking the API server (response time not impacted)
- **SC-004**: Context window automatically maintains exactly the 20 most recent messages when conversation exceeds 20 messages
- **SC-005**: System successfully creates and initializes database on first startup without manual intervention
- **SC-006**: Database operations handle concurrent requests without race conditions or data corruption
- **SC-007**: Migration system successfully updates database schema on application upgrades without data loss

## Assumptions *(mandatory)*

- SQLite is sufficient for MVP single-user deployment (no need for PostgreSQL initially)
- Conversation history is stored locally on the server (no cloud sync required)
- Single conversation per user in MVP (multi-conversation UI can be added later)
- Messages are text-only (no image/file attachments in MVP)
- Database file location is configurable via environment variable
- All timestamps are stored in UTC
- SQLAlchemy ORM is used for all database interactions
- Alembic is used for database migrations

## Dependencies

### Existing Systems

- **Configuration System** (src/haia/config.py): Provides database URL configuration
- **LLM Abstraction Layer** (src/haia/llm/): Consumes conversation context for LLM requests

### External Libraries

- `sqlalchemy[asyncio]>=2.0`: Async ORM for database operations
- `aiosqlite>=0.17`: Async SQLite driver
- `alembic>=1.12`: Database migration tool

### Future Dependencies

- **PydanticAI Agent** (future): Will consume conversation history for agent context
- **Chat API** (future): Will call database layer to store/retrieve messages

## Out of Scope

The following are explicitly **not** included in this feature:

- Multi-user support (single user only in MVP)
- User authentication/authorization
- Conversation sharing or export
- Search functionality within conversations
- Message editing or deletion
- Conversation branching or forking
- Real-time sync across devices
- Database encryption at rest
- PostgreSQL or other database backends (SQLite only)
- Message attachments (images, files, etc.)
- Conversation tags or categories
- Automatic conversation titles (must be set manually or generated later)
