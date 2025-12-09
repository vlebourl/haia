"""Context optimization module for memory deduplication, re-ranking, and token budgeting."""

from haia.context.access_tracker import AccessTracker
from haia.context.budget_manager import BudgetManager
from haia.context.deduplicator import Deduplicator
from haia.context.models import (
    AccessMetadata,
    DeduplicationResult,
    RelevanceScore,
    ScoreWeights,
    TokenBudget,
    TruncationStrategy,
)
from haia.context.ranker import Ranker

# Rebuild models to resolve forward references
try:
    from haia.embedding.models import RetrievalResult  # noqa: F401

    DeduplicationResult.model_rebuild()
except ImportError:
    pass  # RetrievalResult not yet available

__all__ = [
    "AccessMetadata",
    "AccessTracker",
    "BudgetManager",
    "Deduplicator",
    "DeduplicationResult",
    "Ranker",
    "RelevanceScore",
    "ScoreWeights",
    "TokenBudget",
    "TruncationStrategy",
]
