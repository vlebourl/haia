"""Token budget management for context optimization.

This module provides token counting and budget enforcement to prevent
excessive LLM costs by limiting the amount of memory context included
in prompts.

Usage:
    manager = BudgetManager(model_name="claude-sonnet-4")

    # Count tokens
    token_count = manager.count_tokens("Some text")

    # Apply budget to memories
    limited_memories = manager.apply_budget(
        memories=retrieval_results,
        token_budget=2000,
        strategy=TruncationStrategy.HARD_CUTOFF,
    )
"""

import logging
from functools import lru_cache
from typing import Optional

try:
    import tiktoken
except ImportError:
    tiktoken = None

from haia.context.models import TruncationStrategy
from haia.embedding.models import RetrievalResult
from haia.extraction.models import ExtractedMemory

logger = logging.getLogger(__name__)


class BudgetManager:
    """Manages token budgets for memory retrieval.

    Provides token counting and budget enforcement strategies to control
    LLM costs by limiting context size.
    """

    def __init__(
        self,
        model_name: str = "claude-sonnet-4",
        default_budget: int = 2000,
        token_buffer: int = 50,
    ):
        """Initialize budget manager.

        Args:
            model_name: Model name for token encoding (default: claude-sonnet-4)
            default_budget: Default token budget if not specified (default: 2000)
            token_buffer: Reserve buffer for system overhead (default: 50)
        """
        self.model_name = model_name
        self.default_budget = default_budget
        self.token_buffer = token_buffer

        # Initialize tiktoken encoder
        if tiktoken is None:
            logger.warning(
                "tiktoken not installed - using approximate token counting (4 chars/token)"
            )
            self.encoder = None
        else:
            try:
                # Try to get model-specific encoder, fallback to cl100k_base (GPT-4/Claude)
                self.encoder = tiktoken.encoding_for_model("gpt-4")
            except KeyError:
                self.encoder = tiktoken.get_encoding("cl100k_base")

        logger.info(
            f"BudgetManager initialized: model={model_name}, "
            f"default_budget={default_budget}, buffer={token_buffer}"
        )

    @lru_cache(maxsize=1024)
    def count_tokens(self, text: str) -> int:
        """Count tokens in text using tiktoken.

        Uses LRU cache for performance with repeated text.

        Args:
            text: Text to count tokens for

        Returns:
            Token count
        """
        if not text:
            return 0

        if self.encoder is not None:
            # Use tiktoken for accurate counting
            tokens = self.encoder.encode(text)
            return len(tokens)
        else:
            # Fallback: approximate as 4 characters per token
            return max(1, len(text) // 4)

    def count_tokens_for_memory(self, memory: ExtractedMemory) -> int:
        """Count tokens for an entire memory including metadata.

        Includes content, memory type, confidence, and other metadata.

        Args:
            memory: Memory to count tokens for

        Returns:
            Total token count
        """
        # Count content tokens
        content_tokens = self.count_tokens(memory.content)

        # Add metadata overhead (type, confidence, timestamps, etc.)
        # Approximate: ~20 tokens for metadata
        metadata_tokens = 20

        return content_tokens + metadata_tokens

    def estimate_total_tokens(self, memories: list[RetrievalResult]) -> int:
        """Estimate total tokens for a list of memories.

        Uses token_count field if available, otherwise calculates.

        Args:
            memories: List of retrieval results

        Returns:
            Total estimated token count
        """
        total = 0
        for memory in memories:
            if memory.token_count is not None:
                total += memory.token_count
            else:
                # Calculate if not cached
                token_count = self.count_tokens_for_memory(memory.memory)
                memory.token_count = token_count  # Cache for next time
                total += token_count

        return total

    def calculate_budget_margin(
        self, memories: list[RetrievalResult], budget: int
    ) -> int:
        """Calculate remaining budget margin after including memories.

        Args:
            memories: Memories to include
            budget: Token budget

        Returns:
            Remaining tokens (positive = under budget, negative = over budget)
        """
        total_tokens = self.estimate_total_tokens(memories)
        return budget - total_tokens

    def apply_budget(
        self,
        memories: list[RetrievalResult],
        token_budget: Optional[int] = None,
        strategy: TruncationStrategy = TruncationStrategy.HARD_CUTOFF,
    ) -> list[RetrievalResult]:
        """Apply token budget to memory list.

        Args:
            memories: Retrieval results to apply budget to
            token_budget: Maximum token budget (uses default if None)
            strategy: Truncation strategy (HARD_CUTOFF or TRUNCATE)

        Returns:
            Filtered/truncated memories that fit within budget
        """
        if not memories:
            return []

        # Handle explicit zero budget
        if token_budget is not None and token_budget == 0:
            logger.debug("Zero token budget specified - returning empty list")
            return []

        budget = token_budget if token_budget is not None else self.default_budget

        # Adaptive buffer: don't apply buffer for small budgets
        if budget < 100:
            # No buffer for tiny budgets to avoid making them unusable
            effective_budget = budget
            logger.debug(f"Small budget ({budget} tokens) - no buffer applied")
        else:
            # Standard buffer for normal budgets
            effective_budget = budget - self.token_buffer
            logger.debug(
                f"Budget: {budget} tokens, buffer: {self.token_buffer}, "
                f"effective: {effective_budget}"
            )

        if effective_budget <= 0:
            logger.warning(f"Token budget too small after buffer: {effective_budget}")
            return []

        # Check if all memories fit
        total_tokens = self.estimate_total_tokens(memories)
        if total_tokens <= effective_budget:
            # All fit - no truncation needed
            return memories

        # Apply strategy
        if strategy == TruncationStrategy.HARD_CUTOFF:
            return self._apply_hard_cutoff(memories, effective_budget)
        elif strategy == TruncationStrategy.TRUNCATE:
            return self._apply_truncate(memories, effective_budget)
        else:
            logger.warning(f"Unknown strategy {strategy}, using HARD_CUTOFF")
            return self._apply_hard_cutoff(memories, effective_budget)

    def _apply_hard_cutoff(
        self, memories: list[RetrievalResult], budget: int
    ) -> list[RetrievalResult]:
        """Apply HARD_CUTOFF strategy: Remove memories that don't fit.

        Takes memories in order (by rank) until budget is exhausted.

        Args:
            memories: Memories to filter
            budget: Effective token budget

        Returns:
            Memories that fit within budget
        """
        result = []
        current_tokens = 0

        for memory in memories:
            # Get or calculate token count
            if memory.token_count is None:
                memory.token_count = self.count_tokens_for_memory(memory.memory)

            # Check if this memory fits
            if current_tokens + memory.token_count <= budget:
                result.append(memory)
                current_tokens += memory.token_count
                memory.budget_enforced = True
            else:
                # Budget exhausted
                break

        logger.debug(
            f"HARD_CUTOFF: Kept {len(result)}/{len(memories)} memories "
            f"({current_tokens}/{budget} tokens)"
        )

        return result

    def _apply_truncate(
        self, memories: list[RetrievalResult], budget: int
    ) -> list[RetrievalResult]:
        """Apply TRUNCATE strategy: Shorten content to fit more memories.

        Distributes budget across memories, truncating content as needed.

        Args:
            memories: Memories to truncate
            budget: Effective token budget

        Returns:
            Truncated memories that fit within budget
        """
        if not memories:
            return []

        # Strategy: Allocate budget proportionally to relevance scores
        total_relevance = sum(m.relevance_score for m in memories)
        result = []
        current_tokens = 0

        # Adaptive minimum: don't enforce minimum if budget is too small
        min_per_memory = 50 if budget >= (50 * len(memories)) else max(10, budget // len(memories))

        for memory in memories:
            # Check if we have budget left
            if current_tokens >= budget:
                break

            # Allocate budget proportional to relevance
            memory_budget = int((memory.relevance_score / total_relevance) * budget)

            # Apply adaptive minimum budget per memory
            memory_budget = max(min_per_memory, memory_budget)

            # Don't exceed remaining budget
            remaining_budget = budget - current_tokens
            memory_budget = min(memory_budget, remaining_budget)

            # Get current token count
            if memory.token_count is None:
                memory.token_count = self.count_tokens_for_memory(memory.memory)

            if memory.token_count <= memory_budget:
                # Fits without truncation
                result.append(memory)
                current_tokens += memory.token_count
                memory.budget_enforced = True
            else:
                # Truncate content
                truncated_memory = self.truncate_memory_content(
                    memory.memory, max_tokens=memory_budget
                )
                memory.memory = truncated_memory
                memory.token_count = memory_budget
                memory.budget_enforced = True
                result.append(memory)
                current_tokens += memory_budget

            # Stop if budget exhausted
            if current_tokens >= budget:
                break

        logger.debug(
            f"TRUNCATE: Processed {len(result)}/{len(memories)} memories "
            f"({current_tokens}/{budget} tokens)"
        )

        return result

    def truncate_memory_content(
        self, memory: ExtractedMemory, max_tokens: int
    ) -> ExtractedMemory:
        """Truncate memory content to fit within token budget.

        Preserves metadata, only truncates content field.

        Args:
            memory: Memory to truncate
            max_tokens: Maximum tokens for content

        Returns:
            New memory with truncated content
        """
        # Account for metadata overhead (~20 tokens)
        content_budget = max_tokens - 20

        if content_budget <= 0:
            # Minimum content
            truncated_content = memory.content[:50] + "..."
        else:
            # Binary search for max length that fits budget
            content = memory.content
            current_tokens = self.count_tokens(content)

            if current_tokens <= content_budget:
                # Already fits
                return memory

            # Estimate character budget (4 chars/token)
            char_budget = content_budget * 4

            # Truncate with ellipsis
            truncated_content = content[:char_budget] + "..."

            # Fine-tune if needed
            while self.count_tokens(truncated_content) > content_budget and len(
                truncated_content
            ) > 10:
                truncated_content = truncated_content[:-10] + "..."

        # Create new memory with truncated content
        return ExtractedMemory(
            memory_id=memory.memory_id,
            memory_type=memory.memory_type,
            content=truncated_content,
            confidence=memory.confidence,
            source_conversation_id=memory.source_conversation_id,
            extraction_timestamp=memory.extraction_timestamp,
            category=memory.category,
            metadata=memory.metadata,
        )
