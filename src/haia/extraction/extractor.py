"""Memory extraction service using PydanticAI.

This module implements the core extraction logic using a PydanticAI agent
configured with structured output for reliable memory extraction.
"""

import logging
import time
from typing import Any

from pydantic import ValidationError
from pydantic_ai import Agent
from pydantic_ai.models import KnownModelName

from haia.extraction.models import ConversationTranscript, ExtractionResult
from haia.extraction.prompts import format_transcript, system_prompt

logger = logging.getLogger(__name__)


class ExtractionService:
    """Service for extracting memories from conversation transcripts using PydanticAI."""

    def __init__(
        self,
        model: KnownModelName | str = "anthropic:claude-haiku-4-5-20251001",
        min_confidence: float = 0.6,
    ):
        """Initialize extraction service with PydanticAI agent.

        Session 10: Increased min_confidence from 0.4 to 0.6 for dynamic types (G4: High Confidence).

        Args:
            model: LLM model to use (e.g., 'anthropic:claude-haiku-4-5-20251001',
                   'ollama:qwen2.5-coder', 'ollama:llama3.1')
            min_confidence: Minimum confidence threshold for memories (default: 0.6)
        """
        self.model = model
        self.min_confidence = min_confidence

        # Configure PydanticAI Agent with structured output
        self.agent: Agent[None, ExtractionResult] = Agent(
            model=model,
            output_type=ExtractionResult,
            system_prompt=system_prompt(),
        )

        logger.info(
            f"ExtractionService initialized with model={model}, "
            f"min_confidence={min_confidence}"
        )

    async def extract_memories(
        self, transcript: ConversationTranscript
    ) -> ExtractionResult:
        """Extract memories from a conversation transcript.

        Args:
            transcript: Conversation transcript to analyze

        Returns:
            ExtractionResult with extracted memories (confidence e min_threshold)

        Note:
            Returns partial results on validation errors. Logs all extraction events.
        """
        start_time = time.time()
        conversation_id = transcript.conversation_id

        logger.info(
            f"Starting extraction for conversation_id={conversation_id}, "
            f"messages={transcript.message_count}"
        )

        try:
            # Format transcript for LLM
            user_prompt = format_transcript(transcript)

            # Run PydanticAI agent
            result = await self.agent.run(user_prompt)

            # Extract data from agent result
            extraction_result = result.output

            # Validate and filter memories by confidence threshold
            validated_memories = [
                memory
                for memory in extraction_result.memories
                if memory.confidence >= self.min_confidence
            ]

            # Calculate extraction duration
            duration = time.time() - start_time

            # Create final result
            final_result = ExtractionResult(
                conversation_id=conversation_id,
                memories=validated_memories,
                extraction_duration=duration,
                model_used=self.model,
            )

            logger.info(
                f"Extraction complete for conversation_id={conversation_id}, "
                f"duration={duration:.2f}s, "
                f"memory_count={len(validated_memories)}, "
                f"filtered_count={len(extraction_result.memories) - len(validated_memories)}"
            )

            return final_result

        except ValidationError as e:
            duration = time.time() - start_time
            logger.error(
                f"Validation error for conversation_id={conversation_id}: {e}",
                exc_info=True,
            )
            return ExtractionResult(
                conversation_id=conversation_id,
                memories=[],
                extraction_duration=duration,
                model_used=self.model,
                error=f"Validation error: {str(e)}",
            )

        except Exception as e:
            duration = time.time() - start_time
            logger.error(
                f"Extraction failed for conversation_id={conversation_id}: {e}",
                exc_info=True,
            )
            return ExtractionResult(
                conversation_id=conversation_id,
                memories=[],
                extraction_duration=duration,
                model_used=self.model,
                error=str(e),
            )

    async def extract_batch(
        self, transcripts: list[ConversationTranscript], max_concurrency: int = 5
    ) -> list[ExtractionResult]:
        """Extract memories from multiple transcripts in parallel.

        Args:
            transcripts: List of conversation transcripts
            max_concurrency: Maximum number of concurrent extractions (default: 5)

        Returns:
            List of ExtractionResult objects in same order as input

        Note:
            Uses asyncio semaphore to limit concurrency and avoid overwhelming LLM API.
        """
        import asyncio

        logger.info(
            f"Starting batch extraction for {len(transcripts)} transcripts, "
            f"max_concurrency={max_concurrency}"
        )

        semaphore = asyncio.Semaphore(max_concurrency)

        async def extract_with_semaphore(
            transcript: ConversationTranscript,
        ) -> ExtractionResult:
            async with semaphore:
                return await self.extract_memories(transcript)

        results = await asyncio.gather(
            *[extract_with_semaphore(t) for t in transcripts],
            return_exceptions=False,
        )

        successful = sum(1 for r in results if r.is_successful)
        total_memories = sum(r.memory_count for r in results)

        logger.info(
            f"Batch extraction complete: {successful}/{len(transcripts)} successful, "
            f"total_memories={total_memories}"
        )

        return results
