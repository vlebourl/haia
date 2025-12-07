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

from haia.api.deps import get_agent, get_conversation_tracker, get_correlation_id
from haia.api.models.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    TokenUsage,
)
from haia.memory.tracker import ConversationTracker

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


async def stream_chat_response(
    request: ChatCompletionRequest,
    agent: Agent,
    correlation_id: str,
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

        # Calculate prompt tokens (rough estimate)
        prompt_tokens = sum(len(msg["content"].split()) for msg in agent_messages)

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
            message_history=agent_messages[:-1],
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

    # Check streaming mode
    if request.stream:
        # Return SSE streaming response
        return StreamingResponse(
            stream_chat_response(request, agent, correlation_id),
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

        logger.debug(
            f"[{correlation_id}] Sending {len(agent_messages)} messages to agent"
        )

        # Call PydanticAI agent
        result = await agent.run(
            user_prompt=agent_messages[-1]["content"],  # Last message is the user prompt
            message_history=agent_messages[:-1],  # Previous messages are history
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
