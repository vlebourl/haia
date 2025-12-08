"""Confidence scoring algorithms for memory extraction.

This module implements multi-factor confidence calculation combining
LLM-assigned base confidence with deterministic signals like explicitness,
mention frequency, and contradictions.
"""

from typing import Any


class ConfidenceCalculator:
    """Calculator for memory extraction confidence scores."""

    def __init__(
        self,
        min_threshold: float = 0.4,
        explicit_boost: float = 0.1,
        multi_mention_boost: float = 0.05,
        contradiction_penalty: float = 0.3,
        correction_confidence: float = 0.8,
    ):
        """Initialize confidence calculator with configurable parameters.

        Args:
            min_threshold: Minimum confidence to retain memory (default: 0.4)
            explicit_boost: Boost for explicit statements (default: 0.1)
            multi_mention_boost: Boost per additional mention (default: 0.05)
            contradiction_penalty: Penalty for contradictions (default: 0.3)
            correction_confidence: Fixed confidence for corrections (default: 0.8)
        """
        self.min_threshold = min_threshold
        self.explicit_boost = explicit_boost
        self.multi_mention_boost = multi_mention_boost
        self.contradiction_penalty = contradiction_penalty
        self.correction_confidence = correction_confidence

    def calculate(
        self,
        base_confidence: float,
        is_explicit: bool = False,
        mention_count: int = 1,
        has_contradiction: bool = False,
        is_correction: bool = False,
    ) -> float:
        """Calculate final confidence score from multiple factors.

        Args:
            base_confidence: LLM-assigned base confidence (0.0-1.0)
            is_explicit: Whether statement contains explicit indicators
            mention_count: Number of times mentioned (e1)
            has_contradiction: Whether conflicts with existing memory
            is_correction: Whether this is a correction pattern

        Returns:
            Final confidence score clamped to [0.0, 1.0]

        Algorithm:
            1. If correction: return fixed correction_confidence (0.8)
            2. Start with base_confidence
            3. Add explicit_boost if is_explicit
            4. Add multi_mention_boost * (mention_count - 1), max 0.2
            5. Subtract contradiction_penalty if has_contradiction
            6. Clamp result to [0.0, 1.0]
        """
        if is_correction:
            return self.correction_confidence

        confidence = base_confidence

        if is_explicit:
            confidence += self.explicit_boost

        # Multi-mention boost: +0.05 per additional mention, max +0.2
        if mention_count > 1:
            boost = self.multi_mention_boost * (mention_count - 1)
            confidence += min(boost, 0.2)

        if has_contradiction:
            confidence -= self.contradiction_penalty

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, confidence))


def calculate_confidence(
    base: float,
    is_explicit: bool = False,
    mention_count: int = 1,
    has_contradiction: bool = False,
    is_correction: bool = False,
) -> float:
    """Convenience function for confidence calculation.

    This is a stateless wrapper around ConfidenceCalculator.calculate()
    using default parameters.

    Args:
        base: LLM-assigned base confidence (0.0-1.0)
        is_explicit: Whether statement contains explicit indicators
        mention_count: Number of times mentioned (e1)
        has_contradiction: Whether conflicts with existing memory
        is_correction: Whether this is a correction pattern

    Returns:
        Final confidence score clamped to [0.0, 1.0]

    Examples:
        >>> calculate_confidence(0.7, is_explicit=True)
        0.8
        >>> calculate_confidence(0.6, mention_count=3)
        0.7
        >>> calculate_confidence(0.8, has_contradiction=True)
        0.5
        >>> calculate_confidence(0.5, is_correction=True)
        0.8
    """
    calculator = ConfidenceCalculator()
    return calculator.calculate(
        base_confidence=base,
        is_explicit=is_explicit,
        mention_count=mention_count,
        has_contradiction=has_contradiction,
        is_correction=is_correction,
    )


def detect_multi_mentions(
    content: str, conversation_messages: list[dict[str, Any]]
) -> int:
    """Detect how many times similar information appears in conversation.

    Args:
        content: The memory content to search for
        conversation_messages: List of messages from conversation

    Returns:
        Number of times content appears (minimum 1)

    Note:
        This is a simple keyword-based implementation. More sophisticated
        approaches could use semantic similarity, but that adds complexity
        and LLM calls. For MVP, simple keyword matching is sufficient.
    """
    # Extract key terms from content (simple approach: split and filter)
    # In production, this could use NLP techniques, but keeping it simple for MVP
    key_terms = [
        word.lower()
        for word in content.split()
        if len(word) > 4  # Filter short words
        and word.lower()
        not in {"about", "using", "prefer", "prefers", "cluster", "server"}
    ]

    if not key_terms:
        return 1  # No meaningful terms found

    mention_count = 0
    for msg in conversation_messages:
        msg_content = msg.get("content", "").lower()
        # Check if any key terms appear in message
        if any(term in msg_content for term in key_terms):
            mention_count += 1

    return max(1, mention_count)  # Minimum 1


def detect_contradictions(
    new_memory: dict[str, Any], existing_memories: list[dict[str, Any]]
) -> tuple[bool, list[str]]:
    """Detect if new memory contradicts existing memories.

    Args:
        new_memory: Memory being extracted (dict with 'content', 'memory_type')
        existing_memories: List of previously extracted memories

    Returns:
        Tuple of (has_contradiction, list of contradicting memory IDs)

    Note:
        This is a placeholder for MVP. Full implementation would require:
        - Semantic similarity comparison
        - Domain-specific contradiction rules
        - LLM-based contradiction detection

        For MVP, we rely on LLM to mark contradictions in metadata.
    """
    # Placeholder: In MVP, LLM should provide contradiction info in metadata
    # This function will be enhanced in Phase 6 (US4: Contradiction Detection)
    return False, []


def detect_correction_patterns(text: str) -> bool:
    """Detect if text contains correction patterns.

    Args:
        text: Message content to analyze

    Returns:
        True if text contains correction indicators

    Examples:
        >>> detect_correction_patterns("Actually, I meant Docker not Podman")
        True
        >>> detect_correction_patterns("I prefer Docker")
        False
    """
    correction_indicators = [
        "actually",
        "i meant",
        "correction",
        "sorry",
        "i misspoke",
        "not ",
        "no wait",
        "let me correct",
        "to be clear",
    ]

    text_lower = text.lower()
    return any(indicator in text_lower for indicator in correction_indicators)
