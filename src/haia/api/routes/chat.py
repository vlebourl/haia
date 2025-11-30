"""Chat completions API endpoint.

Implements OpenAI-compatible /v1/chat/completions endpoint for HAIA.
"""

import json
import logging
import uuid
from typing import AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from haia.api.deps import get_agent, get_correlation_id, get_db
from haia.api.models.chat import (
    ChatCompletionChunk,
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
    TokenUsage,
)
from haia.db.repository import ConversationRepository

logger = logging.getLogger(__name__)

router = APIRouter()


async def stream_chat_response(
    request: ChatCompletionRequest,
    agent: Agent,
    db: AsyncSession,
    correlation_id: str,
) -> AsyncGenerator[str, None]:
    """Stream chat completion response as Server-Sent Events.

    Args:
        request: Chat completion request
        agent: PydanticAI agent instance
        db: Database session
        correlation_id: Correlation ID for tracing

    Yields:
        SSE-formatted chunk strings with data: prefix

    Note:
        Handles graceful disconnection and saves accumulated response to database.
    """
    chunk_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"
    accumulated_content = ""
    prompt_tokens = 0
    completion_tokens = 0

    try:
        # Initialize conversation repository
        repo = ConversationRepository(db)

        # Create conversation
        conversation = await repo.create_conversation()
        conversation_id = conversation.id

        logger.debug(f"[{correlation_id}] Created conversation ID: {conversation_id}")

        # Save user messages to database
        for msg in request.messages:
            await repo.add_message(conversation_id, msg.role, msg.content)

        # Get context messages
        context_messages = await repo.get_context_messages(conversation_id, limit=20)

        # Convert to agent format
        agent_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in context_messages
        ]

        # Calculate prompt tokens
        prompt_tokens = sum(len(msg["content"].split()) for msg in agent_messages)

        # Send first chunk with role
        first_chunk = ChatCompletionChunk.from_delta(
            content="",
            model=request.model,
            chunk_id=chunk_id,
            role="assistant",
        )
        yield f"data: {first_chunk.model_dump_json()}\n\n"

        # Stream agent response
        async for content_delta in agent.run_stream(
            user_prompt=agent_messages[-1]["content"],
            message_history=agent_messages[:-1],
        ):
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

        # Save accumulated response to database
        await repo.add_message(conversation_id, "assistant", accumulated_content)
        await db.commit()

        logger.info(
            f"[{correlation_id}] Streaming complete: "
            f"conversation_id={conversation_id}, tokens={prompt_tokens + completion_tokens}"
        )

    except GeneratorExit:
        # Client disconnected - save what we have
        logger.warning(
            f"[{correlation_id}] Client disconnected during streaming. "
            f"Accumulated {len(accumulated_content)} characters."
        )
        # Attempt to save partial response
        try:
            if accumulated_content:
                await repo.add_message(conversation_id, "assistant", accumulated_content)
                await db.commit()
        except Exception as save_error:
            logger.error(f"[{correlation_id}] Failed to save partial response: {save_error}")
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
        await db.rollback()


@router.post(
    "/v1/chat/completions",
    summary="Create chat completion",
    description="OpenAI-compatible chat completions endpoint for HAIA (streaming and non-streaming)",
)
async def chat_completions(
    request: ChatCompletionRequest,
    agent: Agent = Depends(get_agent),
    db: AsyncSession = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
):
    """Process chat completion request with HAIA agent.

    Args:
        request: Chat completion request with messages and parameters
        agent: PydanticAI agent instance
        db: Database session for persistence
        correlation_id: Correlation ID for request tracing

    Returns:
        ChatCompletionResponse for non-streaming, StreamingResponse for streaming

    Raises:
        HTTPException: If conversation not found or LLM error occurs
    """
    logger.info(
        f"[{correlation_id}] Processing chat completion request: "
        f"model={request.model}, messages={len(request.messages)}, stream={request.stream}"
    )

    # Check streaming mode
    if request.stream:
        # Return SSE streaming response
        return StreamingResponse(
            stream_chat_response(request, agent, db, correlation_id),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",  # Disable nginx buffering
            },
        )

    try:
        # Initialize conversation repository
        repo = ConversationRepository(db)

        # Create or get conversation
        # For now, always create a new conversation for each request
        # TODO: In User Story 3, handle conversation ID from request headers
        conversation = await repo.create_conversation()
        conversation_id = conversation.id

        logger.debug(f"[{correlation_id}] Created conversation ID: {conversation_id}")

        # Save all user messages from request to database
        # Note: The request may contain full conversation history
        for msg in request.messages:
            await repo.add_message(conversation_id, msg.role, msg.content)

        logger.debug(
            f"[{correlation_id}] Saved {len(request.messages)} messages to conversation {conversation_id}"
        )

        # Get context messages for agent (20 most recent)
        context_messages = await repo.get_context_messages(conversation_id, limit=20)

        # Convert database messages to format for agent
        agent_messages = [
            {"role": msg.role, "content": msg.content}
            for msg in context_messages
        ]

        logger.debug(
            f"[{correlation_id}] Sending {len(agent_messages)} messages to agent"
        )

        # Call PydanticAI agent
        result = await agent.run(
            user_prompt=agent_messages[-1]["content"],  # Last message is the user prompt
            message_history=agent_messages[:-1],  # Previous messages are history
        )

        # Extract response content
        assistant_content = result.data

        logger.info(
            f"[{correlation_id}] Agent returned response: "
            f"{len(assistant_content)} characters"
        )

        # Save assistant response to database
        await repo.add_message(conversation_id, "assistant", assistant_content)

        # Commit transaction
        await db.commit()

        logger.debug(f"[{correlation_id}] Committed transaction for conversation {conversation_id}")

        # Calculate token usage (rough estimate for now)
        # TODO: Use actual token counting in polish phase
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

    except ValueError as e:
        # Database validation errors (invalid role, conversation not found, etc.)
        logger.error(f"[{correlation_id}] Validation error: {e}")
        raise HTTPException(status_code=400, detail=str(e))

    except Exception as e:
        # Rollback transaction on error
        await db.rollback()
        logger.error(
            f"[{correlation_id}] Error processing chat completion: {e}",
            exc_info=True,
        )
        raise HTTPException(
            status_code=500,
            detail="Internal server error processing chat completion",
        )
