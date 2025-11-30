# Feature Specification: LLM Abstraction Layer

**Feature Branch**: `001-llm-abstraction`
**Created**: 2025-11-30
**Status**: Draft
**Input**: User description: "LLM Abstraction Layer"

## User Scenarios & Testing *(mandatory)*

<!--
  IMPORTANT: User stories should be PRIORITIZED as user journeys ordered by importance.
  Each user story/journey must be INDEPENDENTLY TESTABLE - meaning if you implement just ONE of them,
  you should still have a viable MVP (Minimum Viable Product) that delivers value.

  Assign priorities (P1, P2, P3, etc.) to each story, where P1 is the most critical.
  Think of each story as a standalone slice of functionality that can be:
  - Developed independently
  - Tested independently
  - Deployed independently
  - Demonstrated to users independently
-->

### User Story 1 - Initialize Single LLM Provider (Priority: P1)

As a developer, I need to initialize and use a single LLM provider (Anthropic Claude) through a clean interface, so that the chat API can generate responses without knowing implementation details of the LLM provider.

**Why this priority**: This is the absolute minimum needed for MVP chat functionality. Without this, no AI responses can be generated. All other features depend on this working.

**Independent Test**: Can be fully tested by sending a test message to the LLM client and receiving a valid response. Delivers immediate value by enabling basic chat functionality.

**Acceptance Scenarios**:

1. **Given** valid Anthropic API credentials in configuration, **When** the system initializes the LLM client, **Then** an Anthropic client instance is created successfully
2. **Given** an initialized Anthropic client, **When** a chat message is sent, **Then** a response is received within 30 seconds
3. **Given** an initialized Anthropic client, **When** a chat message with multiple turns is sent, **Then** the conversation context is preserved in the response
4. **Given** an initialized client, **When** token usage information is requested after a chat, **Then** the response includes token counts (prompt tokens, completion tokens, total tokens)

---

### User Story 2 - Switch LLM Providers via Configuration (Priority: P2)

As a system administrator, I need to switch between different LLM providers (Anthropic, Ollama, OpenAI, Gemini) by only changing configuration settings, so that I can optimize for cost, privacy, or performance without code changes.

**Why this priority**: This validates the abstraction layer design and enables future flexibility. While MVP uses only Anthropic, the architecture must support multiple providers from day one to avoid costly refactoring later.

**Independent Test**: Can be tested by changing a single configuration value (HAIA_MODEL) and verifying the system initializes the correct provider and generates responses. Delivers value by proving the abstraction works.

**Acceptance Scenarios**:

1. **Given** configuration set to "anthropic:claude-haiku-4-5-20251001", **When** the system initializes, **Then** an Anthropic client is created
2. **Given** configuration set to "ollama:qwen2.5-coder", **When** the system initializes, **Then** an Ollama client is created
3. **Given** configuration set to "openai:gpt-4", **When** the system initializes, **Then** an OpenAI client is created
4. **Given** any valid provider configuration, **When** a chat message is sent, **Then** the response format is identical regardless of provider
5. **Given** an invalid provider name in configuration, **When** the system initializes, **Then** a clear error message indicates the unsupported provider

---

### User Story 3 - Handle LLM Provider Errors Gracefully (Priority: P2)

As a user of the chat system, I need informative error messages when the LLM provider fails, so that I understand what went wrong and can take appropriate action (check API key, network connection, etc.).

**Why this priority**: Error handling is critical for production use. Without proper error handling, users face opaque failures and developers cannot diagnose issues efficiently.

**Independent Test**: Can be tested by simulating various failure scenarios (invalid API key, network timeout, rate limits) and verifying appropriate error responses. Delivers value by improving system reliability and debuggability.

**Acceptance Scenarios**:

1. **Given** an invalid API key, **When** a chat request is made, **Then** an authentication error is returned with a message indicating credential issues
2. **Given** a network timeout during LLM call, **When** the timeout occurs, **Then** a timeout error is returned with retry guidance
3. **Given** an API rate limit is exceeded, **When** a chat request is made, **Then** a rate limit error is returned with information about when to retry
4. **Given** the LLM provider returns malformed data, **When** parsing the response, **Then** a validation error is returned with details about the unexpected format
5. **Given** any LLM provider error, **When** the error occurs, **Then** the error includes provider name, error type, and correlation ID for debugging

---

### User Story 4 - Support Streaming Responses (Interface Level) (Priority: P3)

As a future feature developer, I need the LLM client interface to support streaming responses, so that when streaming is implemented in the chat API, no changes to the abstraction layer are needed.

**Why this priority**: While MVP doesn't use streaming, the interface must include streaming methods to avoid breaking changes later. This is preparatory work for post-MVP streaming feature.

**Independent Test**: Can be tested by calling the streaming method and verifying it yields response chunks in the expected format. Delivers value by future-proofing the abstraction layer.

**Acceptance Scenarios**:

1. **Given** an initialized LLM client, **When** the stream method is called with a message, **Then** response chunks are yielded as they arrive
2. **Given** a streaming response in progress, **When** an error occurs mid-stream, **Then** the error is propagated to the caller appropriately
3. **Given** streaming is called with any provider, **When** chunks are received, **Then** the chunk format is consistent across all providers
4. **Given** a completed stream, **When** all chunks are received, **Then** final token usage statistics are available

---

### Edge Cases

- What happens when the LLM provider API changes its response format? The client should validate responses against expected schema and raise a clear error if validation fails.
- How does the system handle extremely long responses that exceed token limits? The client should detect token limit errors and return them as specific error types.
- What happens when switching providers mid-conversation? The conversation history format should be provider-agnostic, allowing seamless provider switching.
- How does the system handle partial responses during network interruptions? Non-streaming calls should fail cleanly with timeout errors; streaming calls should stop yielding and raise an error.
- What happens when a provider is temporarily unavailable? The client should detect provider availability issues and return service unavailable errors with retry guidance.
- How does the system handle concurrent requests to the same LLM provider? The client should support concurrent async calls without resource conflicts.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST provide an abstract base class (LLMClient) defining a common interface for all LLM providers
- **FR-002**: System MUST implement concrete client classes for each provider: AnthropicClient (MVP), OllamaClient (post-MVP), OpenAIClient (post-MVP), GeminiClient (post-MVP)
- **FR-003**: System MUST use a factory pattern to instantiate the correct client based on configuration (HAIA_MODEL environment variable)
- **FR-004**: All LLM client methods MUST be async (non-blocking I/O)
- **FR-005**: All LLM client inputs and outputs MUST use Pydantic models for type safety and validation
- **FR-006**: System MUST support chat completion requests with message history
- **FR-007**: System MUST return responses in a unified format containing: content, model name, token usage statistics
- **FR-008**: System MUST support temperature and other generation parameters in a provider-agnostic way
- **FR-009**: System MUST include streaming interface methods (even if not used in MVP) to support future streaming feature
- **FR-010**: System MUST handle provider-specific errors and map them to unified error types (AuthenticationError, RateLimitError, TimeoutError, ValidationError, ServiceUnavailableError)
- **FR-011**: System MUST log all LLM API calls with correlation IDs, provider name, model, latency, and token usage
- **FR-012**: System MUST validate API responses against expected schema before returning to caller
- **FR-013**: System MUST fail fast at initialization if provider configuration is invalid or credentials are missing
- **FR-014**: System MUST support configurable timeout values for LLM API calls
- **FR-015**: System MUST preserve message role types (system, user, assistant) across all providers

### Key Entities *(include if feature involves data)*

- **Message**: Represents a single message in a conversation. Contains role (system/user/assistant) and content (text). Must be provider-agnostic.
- **LLMResponse**: Unified response format from any LLM provider. Contains generated content, model identifier, and token usage statistics (prompt tokens, completion tokens, total tokens).
- **LLMClient**: Abstract interface defining all operations available for LLM providers. Subclassed by provider-specific implementations.
- **ClientFactory**: Creates the appropriate LLMClient instance based on configuration. Handles provider selection logic.
- **LLMError**: Base error class for all LLM-related errors. Subclassed by specific error types (AuthenticationError, RateLimitError, etc.) to enable appropriate error handling.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Switching LLM providers requires changing only one configuration value (HAIA_MODEL), with zero code changes
- **SC-002**: All provider implementations return responses in identical format, enabling transparent provider switching
- **SC-003**: LLM API calls complete within configured timeout period (default 30 seconds) or fail with timeout error
- **SC-004**: Every LLM API error includes sufficient information (provider, error type, correlation ID) to diagnose root cause
- **SC-005**: The abstraction layer supports adding a new LLM provider with zero changes to existing client code (only new provider implementation needed)
- **SC-006**: All LLM responses are validated against expected schema, preventing malformed data from propagating to application logic
- **SC-007**: Concurrent chat requests to the same provider complete without resource conflicts or race conditions
- **SC-008**: The interface includes streaming methods that will support future streaming implementation without breaking changes

## Assumptions

- **Provider API Stability**: We assume LLM provider APIs (Anthropic, OpenAI, etc.) maintain backward compatibility for their core chat endpoints. If breaking changes occur, we'll need to update provider-specific client implementations.
- **Configuration Management**: We assume a configuration system exists that provides validated settings (API keys, model names, timeouts) before LLM clients are initialized.
- **Error Handling Philosophy**: We assume fail-fast is preferred - invalid configuration or missing credentials should prevent system startup rather than failing silently.
- **Async Runtime**: We assume the application runs in an async context (asyncio event loop) since all LLM operations are async.
- **Message Format**: We assume a simple message format (role + content) is sufficient for all providers. More complex formats (function calling, tool use) are out of scope for MVP.
- **Logging Infrastructure**: We assume a structured logging system exists that can accept correlation IDs and metadata for observability.
- **Token Limits**: We assume each provider has different token limits, but the abstraction layer does not enforce them - the provider's API will return errors if limits are exceeded.
- **Streaming is Future Work**: We assume streaming responses are not used in MVP, but the interface must include streaming methods to avoid breaking changes when streaming is added.

## Dependencies

- **Configuration Management System**: The LLM abstraction layer requires a configuration system (pydantic-settings) to provide API keys, model selections, and timeout values.
- **Logging Infrastructure**: Requires structured logging capabilities to record LLM API calls with metadata.
- **Provider SDKs**: Requires official SDK libraries for each provider (anthropic, openai, google-generativeai packages) and HTTP client for Ollama.
- **Async Runtime**: Requires Python asyncio support (Python 3.11+).
- **Pydantic**: Requires Pydantic v2 for data validation and type safety.

## Out of Scope

The following are explicitly NOT part of this specification:

- **Function Calling / Tool Use**: Advanced LLM features like function calling, tool use, or structured outputs are not part of the MVP abstraction layer. These may be added in future iterations.
- **Embeddings**: This specification covers only chat completion APIs, not embedding APIs.
- **Fine-tuning**: Model fine-tuning or custom model deployment is out of scope.
- **Caching**: Response caching is not part of the LLM abstraction layer (may be added at a higher level if needed).
- **Cost Tracking**: Detailed cost tracking per request is out of scope (token counts are provided, but cost calculation is separate).
- **Prompt Engineering**: Prompt templates, few-shot examples, or prompt optimization are handled at the agent level, not in the LLM abstraction.
- **Multi-modal Support**: Image, audio, or video inputs/outputs are out of scope for MVP.
- **Model Selection Logic**: The abstraction layer accepts a configured model but does not include logic to automatically select the best model for a task.
