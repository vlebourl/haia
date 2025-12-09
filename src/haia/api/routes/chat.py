"""Chat completions API endpoint.

Implements OpenAI-compatible /v1/chat/completions endpoint for HAIA.
Stateless design - client manages conversation history.
"""

import hashlib
import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic_ai import Agent

from haia.api.deps import (
    get_agent,
    get_conversation_tracker,
    get_correlation_id,
    get_neo4j_service,
    get_retrieval_service,
)
from haia.api.models.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    TokenUsage,
)
from haia.embedding.models import RetrievalQuery
from haia.embedding.retrieval_service import RetrievalService
from haia.memory.tracker import ConversationTracker
from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)

router = APIRouter()


async def get_conversation_id(
    request: Request,
    x_conversation_id: str | None = Header(None),
) -> str:
    """Extract or generate conversation ID for boundary detection.

    Args:
        request: FastAPI request object
        x_conversation_id: Optional conversation ID from request header

    Returns:
        Conversation ID (from header or generated from IP + User-Agent)
    """
    if x_conversation_id:
        return x_conversation_id

    # Fallback: Generate ID from IP + User-Agent
    client_ip = request.client.host if request.client else "unknown"
    user_agent = request.headers.get("user-agent", "unknown")
    fallback_str = f"{client_ip}:{user_agent}"

    # Use first 16 characters of SHA-256 hash
    return hashlib.sha256(fallback_str.encode("utf-8")).hexdigest()[:16]


def format_memories_natural_language(retrieval_response) -> str:
    """Format retrieved memories as natural language context for LLM.

    Args:
        retrieval_response: RetrievalResponse with ranked memories

    Returns:
        Formatted memory context string
    """
    if not retrieval_response.has_results:
        return ""

    lines = ["# Relevant Context from Past Conversations\n"]
    lines.append(
        "The following information was learned from previous interactions. "
        "Use this context to provide personalized, informed responses.\n"
    )

    for result in retrieval_response.results:
        memory = result.memory
        memory_type_label = memory.memory_type.replace("_", " ").title()

        # Format based on memory type for natural reading
        if memory.memory_type == "preference":
            lines.append(f"- **Preference**: {memory.content}")
        elif memory.memory_type == "technical_context":
            lines.append(f"- **Technical Context**: {memory.content}")
        elif memory.memory_type == "decision":
            lines.append(f"- **Past Decision**: {memory.content}")
        elif memory.memory_type == "personal_fact":
            lines.append(f"- **Personal Fact**: {memory.content}")
        elif memory.memory_type == "correction":
            lines.append(f"- **Correction**: {memory.content}")
        else:
            lines.append(f"- **{memory_type_label}**: {memory.content}")

        # Add confidence indicator for medium-confidence memories
        if result.memory.confidence < 0.7:
            lines.append(f"  *(Confidence: {result.memory.confidence:.0%})*")

    lines.append(
        "\n**Note**: Use this context naturally. Don't explicitly mention "
        "that you're using past conversation memory unless directly relevant.\n"
    )

    return "\n".join(lines)


async def stream_chat_response(
    request: ChatCompletionRequest,
    agent: Agent,
    correlation_id: str,
    memory_context: str = "",
) -> AsyncGenerator[str, None]:
    """Stream chat completion response as Server-Sent Events.

    Args:
        request: Chat completion request
        agent: PydanticAI agent instance
        correlation_id: Correlation ID for tracing

    Yields:
        SSE-formatted chunk strings with data: prefix
    """
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    accumulated_content = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        # Convert request messages to agent format
        agent_messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Inject memory context if available
        if memory_context:
            memory_message = {"role": "system", "content": memory_context}
            message_history = [memory_message] + agent_messages[:-1]
        else:
            message_history = agent_messages[:-1]

        # Calculate prompt tokens (rough estimate)
        prompt_tokens = sum(len(msg["content"].split()) for msg in agent_messages)
        if memory_context:
            prompt_tokens += len(memory_context.split())

        # Send first chunk with role
        first_chunk = ChatCompletionChunk.from_delta(
            content="",
            model=request.model,
            chunk_id=chunk_id,
            role="assistant",
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        # Stream agent response using PydanticAI's streaming API
        async with agent.run_stream(
            user_prompt=agent_messages[-1]["content"],
            message_history=message_history,
        ) as result:
            async for content_delta in result.stream_text(delta=True):
                accumulated_content += content_delta
                completion_tokens = len(accumulated_content.split())

                # Create and send chunk
                chunk = ChatCompletionChunk.from_delta(
                    content=content_delta,
                    model=request.model,
                    chunk_id=chunk_id,
                )
                yield f"data: {chunk.model_dump_json()}\n\n"

        # Send final chunk with usage statistics
        final_chunk = ChatCompletionChunk.create_final_chunk(
            model=request.model,
            chunk_id=chunk_id,
            usage=TokenUsage(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=prompt_tokens + completion_tokens,
            ),
        )
        yield f"data: {final_chunk.model_dump_json()}\n\n"

        # Send [DONE] marker
        yield "data: [DONE]\n\n"

        logger.info(
            f"[{correlation_id}] Streaming complete: "
            f"tokens={prompt_tokens + completion_tokens}"
        )

    except GeneratorExit:
        # Client disconnected
        logger.warning(
            f"[{correlation_id}] Client disconnected during streaming. "
            f"Accumulated {len(accumulated_content)} characters."
        )
        raise

    except Exception as e:
        # Error during streaming
        logger.error(
            f"[{correlation_id}] Error during streaming: {e}",
            exc_info=True,
        )
        # Send error as final chunk (OpenAI-compatible error handling)
        error_chunk = {
            "id": chunk_id,
            "object": "chat.completion.chunk",
            "choices": [
                {
                    "index": 0,
                    "delta": {},
                    "finish_reason": "error",
                }
            ],
        }
        yield f"data: {json.dumps(error_chunk)}\n\n"
        yield "data: [DONE]\n\n"


@router.post(
    "/v1/chat/completions",
    summary="Create chat completion",
    description="OpenAI-compatible chat completions endpoint for HAIA (streaming and non-streaming)",
)
async def chat_completions(
    request: ChatCompletionRequest,
    agent: Agent = Depends(get_agent),
    tracker: ConversationTracker = Depends(get_conversation_tracker),
    retrieval_service: RetrievalService | None = Depends(get_retrieval_service),
    correlation_id: str = Depends(get_correlation_id),
    conversation_id: str = Depends(get_conversation_id),
):
    """Process chat completion request with HAIA agent.

    Stateless design: Client sends full conversation history in request.messages.

    Args:
        request: Chat completion request with messages and parameters
        agent: PydanticAI agent instance
        tracker: ConversationTracker for boundary detection
        correlation_id: Correlation ID for request tracing
        conversation_id: Conversation ID for boundary detection

    Returns:
        ChatCompletionResponse for non-streaming, StreamingResponse for streaming

    Raises:
        HTTPException: If LLM error occurs
    """
    logger.info(
        f"[{correlation_id}] Processing chat completion request: "
        f"model={request.model}, messages={len(request.messages)}, "
        f"stream={request.stream}, conversation_id={conversation_id}"
    )

    # Process boundary detection BEFORE agent execution
    try:
        # Convert request messages to simple dict format for tracker
        message_dicts = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Check for conversation boundary
        boundary_result = await tracker.process_request(conversation_id, message_dicts)

        if boundary_result.detected:
            logger.info(
                f"[{correlation_id}] Conversation boundary detected: "
                f"reason={boundary_result.reason}, "
                f"idle={boundary_result.idle_duration_seconds}s"
            )

    except Exception as e:
        # Log error but don't block the chat request
        logger.error(
            f"[{correlation_id}] Error in boundary detection: {e}",
            exc_info=True,
        )

    # Retrieve relevant memories (Session 8 - Memory Retrieval)
    # Graceful degradation: If retrieval unavailable or fails, continue without memories
    memory_context = ""
    if retrieval_service is not None and len(request.messages) > 0:
        try:
            # Use last user message as retrieval query
            user_message = request.messages[-1].content
            query = RetrievalQuery(
                query_text=user_message,
                top_k=5,  # Conservative limit to avoid context overflow
                min_similarity=0.65,
                min_confidence=0.4,
            )

            retrieval_response = await retrieval_service.retrieve(query)

            if retrieval_response.has_results:
                memory_context = format_memories_natural_language(retrieval_response)
                logger.info(
                    f"[{correlation_id}] Retrieved {retrieval_response.total_results} memories "
                    f"(latency: {retrieval_response.total_latency_ms:.1f}ms, "
                    f"top relevance: {retrieval_response.results[0].relevance_score:.3f})"
                )
            else:
                logger.debug(f"[{correlation_id}] No relevant memories found")

        except Exception as e:
            # Log error but continue without memories (graceful degradation)
            logger.warning(
                f"[{correlation_id}] Error retrieving memories: {e}. "
                "Continuing without memory context."
            )

    # Check streaming mode
    if request.stream:
        # Return SSE streaming response
        return StreamingResponse(
            stream_chat_response(request, agent, correlation_id, memory_context),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    try:
        # Convert request messages to agent format
        agent_messages = [
            {"role": msg.role, "content": msg.content} for msg in request.messages
        ]

        # Inject memory context if available
        if memory_context:
            # Prepend memory context as a system message to message history
            memory_message = {"role": "system", "content": memory_context}
            message_history = [memory_message] + agent_messages[:-1]
            logger.debug(
                f"[{correlation_id}] Injected memory context ({len(memory_context)} chars)"
            )
        else:
            message_history = agent_messages[:-1]

        logger.debug(
            f"[{correlation_id}] Sending {len(agent_messages)} messages to agent "
            f"(with memory context: {bool(memory_context)})"
        )

        # Call PydanticAI agent
        result = await agent.run(
            user_prompt=agent_messages[-1]["content"],  # Last message is the user prompt
            message_history=message_history,  # Previous messages + memory context
        )

        # Extract response content (PydanticAI uses .output, not .data)
        assistant_content = result.output

        logger.info(
            f"[{correlation_id}] Agent returned response: "
            f"{len(assistant_content)} characters"
        )

        # Calculate token usage (rough estimate for now)
        prompt_tokens = sum(len(msg.content.split()) for msg in request.messages)
        completion_tokens = len(assistant_content.split())

        # Create response using factory method
        response = ChatCompletionResponse.from_agent_result(
            content=assistant_content,
            model=request.model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            finish_reason="stop",
        )

        logger.info(
            f"[{correlation_id}] Returning response: id={response.id}, "
            f"tokens={response.usage.total_tokens}"
        )

        return response

    except Exception as e:
        logger.error(
            f"[{correlation_id}] Error processing chat completion: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing chat completion",
        )


@router.get("/v1/models")
async def list_models():
    """List available models (OpenAI-compatible endpoint).

    Returns a minimal models list for OpenWebUI compatibility.
    """
    return {
        "object": "list",
        "data": [
            {
                "id": "haia",
                "object": "model",
                "created": 1699000000,
                "owned_by": "haia",
            }
        ],
    }


@router.get("/health")
async def health_check(
    neo4j_service: Neo4jService = Depends(get_neo4j_service),
    retrieval_service: RetrievalService | None = Depends(get_retrieval_service),
):
    """Health check endpoint with system status and version information.

    Returns:
        Health status with Neo4j connectivity, retrieval service status, and version info
    """
    neo4j_healthy = await neo4j_service.health_check()

    # Check retrieval service status (Session 8)
    retrieval_status = "disabled"
    if retrieval_service:
        retrieval_healthy = await retrieval_service.health_check()
        retrieval_status = "healthy" if retrieval_healthy else "degraded"

    # Determine overall status
    if neo4j_healthy and (retrieval_status in ["healthy", "disabled"]):
        overall_status = "healthy"
    else:
        overall_status = "degraded"

    return {
        "status": overall_status,
        "version": "1.0.0-session8",
        "features": {
            "memory_extraction": "enabled",  # Session 7
            "memory_retrieval": retrieval_status,  # Session 8
            "multi_factor_scoring": retrieval_status,  # Session 8 US3
        },
        "services": {
            "neo4j": "connected" if neo4j_healthy else "disconnected",
            "ollama_embedding": retrieval_status,
        },
    }
