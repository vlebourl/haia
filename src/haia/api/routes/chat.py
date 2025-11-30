"""Chat completions API endpoint.

Implements OpenAI-compatible /v1/chat/completions endpoint for HAIA.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic_ai import Agent
from sqlalchemy.ext.asyncio import AsyncSession

from haia.api.deps import get_agent, get_correlation_id, get_db
from haia.api.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ChatMessage,
)
from haia.db.repository import ConversationRepository

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post(
    "/v1/chat/completions",
    response_model=ChatCompletionResponse,
    summary="Create chat completion",
    description="OpenAI-compatible chat completions endpoint for HAIA",
)
async def chat_completions(
    request: ChatCompletionRequest,
    agent: Agent = Depends(get_agent),
    db: AsyncSession = Depends(get_db),
    correlation_id: str = Depends(get_correlation_id),
) -> ChatCompletionResponse:
    """Process chat completion request with HAIA agent.

    Args:
        request: Chat completion request with messages and parameters
        agent: PydanticAI agent instance
        db: Database session for persistence
        correlation_id: Correlation ID for request tracing

    Returns:
        ChatCompletionResponse with assistant's response

    Raises:
        HTTPException: If conversation not found or LLM error occurs
    """
    logger.info(
        f"[{correlation_id}] Processing chat completion request: "
        f"model={request.model}, messages={len(request.messages)}, stream={request.stream}"
    )

    # Check streaming mode
    if request.stream:
        # TODO: Implement streaming in User Story 2 (Phase 4)
        raise HTTPException(
            status_code=501,
            detail="Streaming not yet implemented - will be available in User Story 2",
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
