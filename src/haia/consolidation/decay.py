"""
Decay strategies for memory recency scoring.

Implements different mathematical models for calculating how memory "freshness"
decays over time based on access patterns.

Session 14 (US6): Memory Consolidation Lifecycle
"""

import logging
import math
from abc import ABC, abstractmethod
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class DecayStrategy(ABC):
    """
    Abstract base class for memory decay strategies (T101).

    Decay strategies calculate a recency score (0.0-1.0) based on:
    - created_at: When the memory was first created
    - last_accessed: When the memory was most recently accessed (None if never)
    - access_count: Number of times the memory has been retrieved

    Higher scores = more recent/important, Lower scores = older/less important
    """

    @abstractmethod
    def calculate_decay(
        self,
        created_at: datetime,
        last_accessed: datetime | None,
        access_count: int,
    ) -> float:
        """
        Calculate recency score for a memory.

        Args:
            created_at: When memory was created
            last_accessed: When memory was last retrieved (None if never accessed)
            access_count: Number of times memory has been retrieved

        Returns:
            Recency score from 0.0 (very old) to 1.0 (very recent)
        """
        pass

    def _days_since_last_access(
        self, created_at: datetime, last_accessed: datetime | None
    ) -> float:
        """
        Calculate days since last access (or creation if never accessed).

        Args:
            created_at: When memory was created
            last_accessed: When memory was last accessed

        Returns:
            Days elapsed since last access/creation
        """
        reference_time = last_accessed if last_accessed else created_at
        now = datetime.now(timezone.utc)

        # Ensure reference_time is timezone-aware
        if reference_time.tzinfo is None:
            reference_time = reference_time.replace(tzinfo=timezone.utc)

        delta = now - reference_time
        return delta.total_seconds() / 86400.0  # Convert to days


class ExponentialDecay(DecayStrategy):
    """
    Exponential decay with adaptive half-life based on access frequency (T102).

    Frequently accessed memories decay slower than rarely accessed ones.

    Formula:
    - effective_half_life = base_half_life * (1 + log(1 + access_count))
    - decay = 0.5 ** (days_elapsed / effective_half_life)

    Default base_half_life: 43.3 days (approx 6 weeks)
    """

    def __init__(self, base_half_life_days: float = 43.3):
        """
        Initialize exponential decay strategy.

        Args:
            base_half_life_days: Base half-life for decay (default: 43.3 days ≈ 6 weeks)
        """
        self.base_half_life = base_half_life_days
        logger.info(f"ExponentialDecay initialized (base_half_life={base_half_life_days} days)")

    def calculate_decay(
        self,
        created_at: datetime,
        last_accessed: datetime | None,
        access_count: int,
    ) -> float:
        """
        Calculate exponential decay with adaptive half-life.

        Args:
            created_at: When memory was created
            last_accessed: When memory was last accessed
            access_count: Number of accesses

        Returns:
            Decay score 0.0-1.0
        """
        days_elapsed = self._days_since_last_access(created_at, last_accessed)

        # Adaptive half-life: frequently accessed memories decay slower
        # log(1 + access_count) provides diminishing returns for high access counts
        effective_half_life = self.base_half_life * (1 + math.log(1 + access_count))

        # Exponential decay: score = 0.5 ** (time / half_life)
        decay = 0.5 ** (days_elapsed / effective_half_life)

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, decay))


class EbbinghausDecay(DecayStrategy):
    """
    Ebbinghaus forgetting curve decay strategy (T103).

    Based on Hermann Ebbinghaus's research on memory retention.

    Formula:
    - retention = exp(-t / S)
    - S (stability) = base_stability * (1 + 0.5 * access_count)

    Memories with more accesses have higher stability (decay slower).
    """

    def __init__(self, base_stability_days: float = 30.0):
        """
        Initialize Ebbinghaus decay strategy.

        Args:
            base_stability_days: Base stability parameter (default: 30 days)
        """
        self.base_stability = base_stability_days
        logger.info(f"EbbinghausDecay initialized (base_stability={base_stability_days} days)")

    def calculate_decay(
        self,
        created_at: datetime,
        last_accessed: datetime | None,
        access_count: int,
    ) -> float:
        """
        Calculate Ebbinghaus forgetting curve decay.

        Args:
            created_at: When memory was created
            last_accessed: When memory was last accessed
            access_count: Number of accesses

        Returns:
            Retention score 0.0-1.0
        """
        days_elapsed = self._days_since_last_access(created_at, last_accessed)

        # Stability increases with access count (diminishing returns)
        stability = self.base_stability * (1 + 0.5 * access_count)

        # Ebbinghaus forgetting curve: R = e^(-t/S)
        retention = math.exp(-days_elapsed / stability)

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, retention))


class LinearDecay(DecayStrategy):
    """
    Simple linear decay over time with access-based multiplier (T104).

    Easiest to understand and reason about, but less realistic than exponential/Ebbinghaus.

    Formula:
    - base_decay = 1.0 - (days_elapsed / max_days)
    - access_multiplier = 1 + (access_count * 0.05)  # 5% boost per access
    - final_score = base_decay * access_multiplier (clamped to 1.0)
    """

    def __init__(self, max_days: float = 365.0):
        """
        Initialize linear decay strategy.

        Args:
            max_days: Days at which decay reaches 0 (default: 365 days = 1 year)
        """
        self.max_days = max_days
        logger.info(f"LinearDecay initialized (max_days={max_days})")

    def calculate_decay(
        self,
        created_at: datetime,
        last_accessed: datetime | None,
        access_count: int,
    ) -> float:
        """
        Calculate linear decay with access multiplier.

        Args:
            created_at: When memory was created
            last_accessed: When memory was last accessed
            access_count: Number of accesses

        Returns:
            Decay score 0.0-1.0
        """
        days_elapsed = self._days_since_last_access(created_at, last_accessed)

        # Linear decay from 1.0 (day 0) to 0.0 (max_days)
        base_decay = 1.0 - (days_elapsed / self.max_days)

        # Access multiplier: 5% boost per access (diminishing returns via clamping)
        access_multiplier = 1.0 + (access_count * 0.05)

        # Final score with multiplier
        score = base_decay * access_multiplier

        # Clamp to [0.0, 1.0]
        return max(0.0, min(1.0, score))
