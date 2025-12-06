# Feature Specification: OpenAI-Compatible Chat API with Streaming

**Feature Branch**: `003-openai-chat-api`
**Created**: 2025-11-30
**Status**: Completed (with architectural changes)
**Completed**: 2025-12-06
**Input**: User description: "OpenAI-Compatible Chat API with Streaming - FastAPI server exposing /v1/chat/completions endpoint with SSE streaming support, PydanticAI agent integration, conversation history management, and OpenWebUI compatibility"

---

## IMPLEMENTATION NOTE

**Architectural Change**: The final implementation uses a **stateless design** where the client (OpenWebUI) manages conversation history, rather than server-side database persistence as originally specified.

**Rationale**:
- Simpler deployment (no database setup or migrations)
- Standard OpenAI API pattern (clients send full message history)
- OpenWebUI already manages conversation state
- Reduces complexity for MVP

**Impact**: References to database, conversation persistence, and 20-message context windows in this spec reflect the original plan but were not implemented. The stateless approach proved sufficient for the MVP use case.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Basic Chat Interaction (Priority: P1)

A homelab administrator wants to ask HAIA questions about their infrastructure through a chat interface (OpenWebUI or any OpenAI-compatible client). They should be able to send messages and receive responses in real-time.

**Why this priority**: This is the core MVP functionality - without it, HAIA cannot be used at all. This delivers immediate value by making the AI assistant accessible through standard chat interfaces.

**Independent Test**: Can be fully tested by sending a POST request to `/v1/chat/completions` with a simple message and verifying a response is returned. Delivers the fundamental chat interaction capability.

**Acceptance Scenarios**:

1. **Given** a user has OpenWebUI configured with HAIA as a provider, **When** they send a message "Hello, what can you help me with?", **Then** they receive a coherent response explaining HAIA's capabilities within 5 seconds
2. **Given** a user sends a technical question about their homelab, **When** the agent processes the request, **Then** the response is relevant to homelab administration and infrastructure management
3. **Given** a user sends multiple messages in sequence, **When** each message is processed, **Then** responses maintain context from previous messages in the conversation

---

### User Story 2 - Real-Time Streaming Responses (Priority: P1)

A user wants to see HAIA's responses appear word-by-word as they're generated, rather than waiting for the complete response. This provides immediate feedback that the system is working and allows users to start reading before generation completes.

**Why this priority**: Streaming is essential for good user experience with LLMs. Long responses (especially explanations or troubleshooting steps) feel much faster when streaming, and it's a standard expectation in modern chat interfaces.

**Independent Test**: Can be tested by connecting an SSE-compatible client to the endpoint with `stream: true` and verifying that response chunks arrive progressively before the full response completes. Delivers professional-grade chat UX.

**Acceptance Scenarios**:

1. **Given** a user requests streaming mode via the API (`stream: true`), **When** the agent generates a long response, **Then** response chunks arrive via Server-Sent Events as tokens are generated
2. **Given** a streaming response is in progress, **When** the user's client disconnects, **Then** the system gracefully stops generation and cleans up resources
3. **Given** a user's client doesn't support streaming, **When** they send a request without `stream: true`, **Then** they receive the complete response in a single JSON payload

---

### User Story 3 - Persistent Conversation History (Priority: P1)

A user wants their conversations with HAIA to persist across sessions. They should be able to close OpenWebUI, reopen it later, and continue the same conversation with full context.

**Why this priority**: Without persistence, HAIA loses all context on restart, making it nearly useless for ongoing homelab management. This is core to the "conversation database" integration and makes HAIA actually practical for daily use.

**Independent Test**: Can be tested by creating a conversation, sending messages, restarting the server, and verifying that conversation history loads correctly with the 20-message context window. Delivers stateful assistant capability.

**Acceptance Scenarios**:

1. **Given** a user has an existing conversation with 15 messages, **When** they send a new message, **Then** the system loads the previous 15 messages as context for the agent
2. **Given** a conversation has more than 20 messages, **When** a new message is sent, **Then** only the most recent 20 messages are loaded as context (sliding window)
3. **Given** a user creates a new conversation, **When** they send their first message, **Then** a new conversation record is created in the database with a unique ID

---

### User Story 4 - Error Handling and Resilience (Priority: P2)

When something goes wrong (LLM provider unavailable, database error, rate limits), users should receive clear error messages and the system should recover gracefully rather than crashing.

**Why this priority**: Error handling is essential for production use but can be implemented after core functionality works. Users need to understand what went wrong, but this doesn't block basic testing of the happy path.

**Independent Test**: Can be tested by simulating various failure conditions (disconnected Ollama, invalid API key, database down) and verifying appropriate error responses are returned. Delivers production-ready reliability.

**Acceptance Scenarios**:

1. **Given** the configured LLM provider is unavailable, **When** a user sends a message, **Then** they receive a clear error message indicating the AI service is temporarily unavailable (HTTP 503)
2. **Given** the database is unreachable, **When** a user tries to load conversation history, **Then** the system returns an error but doesn't crash, and new messages can still be processed without persistence
3. **Given** a user sends a request with invalid format, **When** the request is validated, **Then** they receive a descriptive error message explaining what's wrong with their request (HTTP 400)
4. **Given** a rate limit is exceeded on the LLM provider, **When** a user sends a message, **Then** they receive a clear error about rate limiting with retry-after guidance (HTTP 429)

---

### User Story 5 - Model Selection and Configuration (Priority: P3)

A homelab administrator wants to configure which AI model HAIA uses without restarting the server. They should be able to switch between Anthropic models (development) and local Ollama models (production) via configuration.

**Why this priority**: This is valuable for flexibility but not essential for MVP. The model can be configured via environment variables at startup initially. Runtime switching is a nice-to-have enhancement.

**Independent Test**: Can be tested by changing the `HAIA_MODEL` environment variable and restarting the server, then verifying that the new model is used. Delivers deployment flexibility across development and production.

**Acceptance Scenarios**:

1. **Given** HAIA is configured with `HAIA_MODEL=anthropic:claude-haiku-4-5-20251001`, **When** a user sends a message, **Then** the request is routed to the Anthropic API
2. **Given** HAIA is configured with `HAIA_MODEL=ollama:qwen2.5-coder`, **When** a user sends a message, **Then** the request is routed to the local Ollama instance
3. **Given** an invalid model configuration is provided, **When** the server starts, **Then** it fails fast with a clear error message indicating the configuration problem

---

### Edge Cases

- **What happens when a conversation has exactly 20 messages?**: All 20 should be loaded as context (boundary condition for context window)
- **What happens when a user sends an extremely long message (>10,000 tokens)?**: System should validate message length and return error before sending to LLM to avoid token limit errors
- **How does the system handle concurrent requests to the same conversation?**: Database should handle concurrent message writes correctly without race conditions
- **What happens when the LLM provider returns a streaming error mid-response?**: System should send an error event via SSE and gracefully close the stream
- **What happens when a user requests a conversation that doesn't exist?**: System should create a new conversation with that ID or return a 404 error with clear message
- **How does the system behave if the database is slow (>5 seconds)?**: Should timeout database operations and return error rather than hanging indefinitely
- **What happens if the agent's system prompt is missing or invalid?**: Should fail fast at startup with clear error message

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST expose an HTTP API endpoint at `/v1/chat/completions` that accepts POST requests with OpenAI-compatible request format
- **FR-002**: System MUST support streaming responses via Server-Sent Events (SSE) when `stream: true` is specified in the request
- **FR-003**: System MUST support non-streaming responses (single JSON response) when `stream: false` or when stream is not specified
- **FR-004**: System MUST initialize a PydanticAI agent with the LLM client from the abstraction layer (Feature 001)
- **FR-005**: System MUST configure the agent with a system prompt defining HAIA's role as a homelab infrastructure assistant
- **FR-006**: System MUST load conversation history from the database before processing each message
- **FR-007**: System MUST apply the 20-message context window when loading conversation history (most recent 20 messages)
- **FR-008**: System MUST save user messages to the database immediately after receiving them
- **FR-009**: System MUST save assistant responses to the database after generation completes
- **FR-010**: System MUST handle conversation IDs - either use existing conversation or create new one
- **FR-011**: System MUST validate incoming requests against OpenAI API schema (messages array, model, temperature, max_tokens, etc.)
- **FR-012**: System MUST return appropriate HTTP status codes (200 for success, 400 for bad request, 429 for rate limit, 500/503 for server errors)
- **FR-013**: System MUST enable CORS to allow web-based chat clients (OpenWebUI) to connect
- **FR-014**: System MUST log all chat requests with correlation IDs for debugging and observability
- **FR-015**: System MUST support the OpenAI API parameters: `messages`, `model`, `temperature`, `max_tokens`, `stream`
- **FR-016**: System MUST gracefully handle LLM provider errors and return user-friendly error messages
- **FR-017**: System MUST gracefully handle database errors without crashing the server
- **FR-018**: System MUST provide dependency injection for database sessions and LLM clients
- **FR-019**: System MUST start up and bind to configurable host and port (from settings)
- **FR-020**: System MUST initialize the database schema on startup if not already initialized
- **FR-021**: System MUST support health check endpoint for monitoring (e.g., `/health`)
- **FR-022**: System MUST validate message content is not empty before processing
- **FR-023**: System MUST handle streaming disconnections gracefully without resource leaks
- **FR-024**: System MUST map internal message format (from database) to OpenAI message format and vice versa

### Key Entities

- **Chat Request**: Represents incoming API request with messages array, model selection, parameters (temperature, max_tokens), and streaming preference
- **Chat Response**: Represents outgoing API response with generated content, finish reason, token usage statistics, and conversation metadata
- **Streaming Chunk**: Represents individual SSE events during streaming response, containing partial content and metadata
- **Agent Context**: Represents the dependency injection context for the PydanticAI agent, including LLM client, database session, and configuration
- **System Prompt**: Defines HAIA's role, capabilities, and behavioral guidelines for the agent
- **Error Response**: Represents error information returned to client, including HTTP status, error type, and user-friendly message

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can send a chat message and receive a response in under 5 seconds for simple queries (95th percentile)
- **SC-002**: Streaming responses begin delivering tokens within 500ms of request (time to first byte)
- **SC-003**: System successfully handles 10 concurrent chat requests without degradation
- **SC-004**: Conversation history loads correctly in 100% of cases when fewer than 20 messages exist
- **SC-005**: Conversation context window correctly limits to 20 most recent messages when more messages exist
- **SC-006**: System achieves 99% uptime during continuous operation for 24 hours
- **SC-007**: All API requests include correlation IDs for tracing in logs (100% coverage)
- **SC-008**: Error responses provide actionable information to users in 100% of failure cases
- **SC-009**: Database operations (save/load messages) complete in under 100ms for conversations with up to 1000 messages
- **SC-010**: System successfully switches between Anthropic and Ollama providers via configuration change with zero code changes
- **SC-011**: OpenWebUI clients can connect and chat without configuration beyond base URL and API key
- **SC-012**: Memory usage remains stable (no memory leaks) during 1000 consecutive chat requests
