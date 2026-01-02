"""
LLM-driven relationship inference between memories.

Automatically discovers connections between memories using LLM analysis
instead of hardcoded rules. Enables "show me related memories" queries.

🔒 P1: Emergence Over Prescription - Relationships discovered, not hardcoded
🔒 P5: Observability - All inferences logged with reasoning
📐 G3: Confidence Thresholds - Only store relationships with confidence >=0.7
"""

import asyncio
import logging
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent

from haia.services.neo4j import Neo4jService

logger = logging.getLogger(__name__)


# Relationship types discovered by LLM (not hardcoded enum)
RelationshipType = Literal[
    "DEPENDS_ON",      # A requires B
    "REPLACED_BY",     # A was replaced by B
    "CONTRADICTS",     # A contradicts B
    "INSPIRED_BY",     # A was inspired by/built upon B
    "COMPLEMENTS",     # A complements B (work together)
    "PART_OF",         # A is part of B
    "SIMILAR_TO",      # A is similar to B
    "EVOLVED_FROM",    # A evolved from B
]


class RelationshipInference(BaseModel):
    """LLM-inferred relationship between two memories."""

    exists: bool = Field(
        ...,
        description="Whether a meaningful relationship exists between the memories",
    )
    relationship_type: Optional[RelationshipType] = Field(
        None,
        description="Type of relationship if exists=True",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score (0.0-1.0) in the relationship",
    )
    reasoning: str = Field(
        ...,
        description="Human-readable explanation of why this relationship exists/doesn't exist",
    )


class RelationshipInferenceService:
    """
    LLM-driven service for inferring relationships between memories.

    Approach:
    1. Use PydanticAI agent to analyze memory pairs
    2. LLM determines relationship type and confidence
    3. Only store relationships with confidence >=0.7 (G3)
    4. Log all decisions for observability (P5)
    """

    def __init__(
        self,
        neo4j_service: Neo4jService,
        model: str = "anthropic:claude-haiku-4-5-20251001",
        min_confidence: float = 0.7,
    ):
        """
        Initialize RelationshipInferenceService.

        Args:
            neo4j_service: Neo4j service for database operations
            model: LLM model for relationship inference (Haiku for cost)
            min_confidence: Minimum confidence to store relationships (default: 0.7)
        """
        self.neo4j = neo4j_service
        self.model = model
        self.min_confidence = min_confidence

        # Create PydanticAI agent for relationship inference
        self.agent: Agent[None, RelationshipInference] = Agent(
            model=self.model,
            output_type=RelationshipInference,
            system_prompt=self._build_system_prompt(),
        )

        logger.info(
            f"RelationshipInferenceService initialized "
            f"(model={model}, min_confidence={min_confidence})"
        )

    def _build_system_prompt(self) -> str:
        """Build system prompt for relationship inference."""
        return """You are an expert at analyzing semantic relationships between pieces of information.

Your task: Analyze two memory entries and determine if a meaningful relationship exists between them.

Available relationship types:
- DEPENDS_ON: First memory requires/depends on the second
- REPLACED_BY: First memory was replaced/superseded by the second
- CONTRADICTS: Memories contain contradictory information
- INSPIRED_BY: First memory was inspired by/built upon the second
- COMPLEMENTS: Memories complement each other (work together)
- PART_OF: First memory is a component/part of the second
- SIMILAR_TO: Memories describe similar concepts/approaches
- EVOLVED_FROM: First memory evolved from the second

Guidelines:
1. Only identify STRONG, clear relationships
2. Avoid forcing relationships when memories are merely tangentially related
3. Provide specific reasoning for your decision
4. Be conservative - it's better to miss a weak relationship than create a false one
5. Consider temporal context if available (dates, sequences)

Output:
- exists: true/false (does a meaningful relationship exist?)
- relationship_type: one of the types above (if exists=true)
- confidence: 0.0-1.0 (how confident are you?)
- reasoning: specific explanation of why/why not
"""

    async def infer_relationship(
        self,
        memory_a_id: str,
        memory_a_content: str,
        memory_a_type: str,
        memory_b_id: str,
        memory_b_content: str,
        memory_b_type: str,
    ) -> Optional[RelationshipInference]:
        """
        Infer relationship between two memories using LLM analysis.

        Args:
            memory_a_id: ID of first memory
            memory_a_content: Content of first memory
            memory_a_type: Type of first memory
            memory_b_id: ID of second memory
            memory_b_content: Content of second memory
            memory_b_type: Type of second memory

        Returns:
            RelationshipInference if relationship found, None otherwise
        """
        prompt = f"""Analyze these two memories and determine if a relationship exists:

Memory A (ID: {memory_a_id[:8]}..., Type: {memory_a_type}):
"{memory_a_content}"

Memory B (ID: {memory_b_id[:8]}..., Type: {memory_b_type}):
"{memory_b_content}"

Does a meaningful relationship exist between these memories? If so, what type and how confident are you?"""

        try:
            result = await self.agent.run(prompt)
            inference = result.output

            # Log the inference decision
            if inference.exists:
                logger.debug(
                    f"Relationship inferred: {memory_a_id[:8]}... "
                    f"-[{inference.relationship_type}]-> {memory_b_id[:8]}... "
                    f"(confidence: {inference.confidence:.2f})"
                )
            else:
                logger.debug(
                    f"No relationship: {memory_a_id[:8]}... <-> {memory_b_id[:8]}... "
                    f"(reasoning: {inference.reasoning[:50]}...)"
                )

            # Only return if exists and meets confidence threshold
            if inference.exists and inference.confidence >= self.min_confidence:
                return inference
            else:
                return None

        except Exception as e:
            logger.error(f"Failed to infer relationship: {e}")
            return None

    async def batch_infer_relationships(
        self,
        memory_pairs: list[tuple[dict, dict]],
    ) -> list[tuple[str, str, RelationshipInference]]:
        """
        Infer relationships for multiple memory pairs in parallel.

        Args:
            memory_pairs: List of (memory_a_dict, memory_b_dict) tuples

        Returns:
            List of (memory_a_id, memory_b_id, inference) tuples for valid relationships
        """
        tasks = []

        for memory_a, memory_b in memory_pairs:
            task = self.infer_relationship(
                memory_a_id=memory_a["memory_id"],
                memory_a_content=memory_a["content"],
                memory_a_type=memory_a["memory_type"],
                memory_b_id=memory_b["memory_id"],
                memory_b_content=memory_b["content"],
                memory_b_type=memory_b["memory_type"],
            )
            tasks.append((memory_a["memory_id"], memory_b["memory_id"], task))

        # Execute all inference tasks in parallel
        results = await asyncio.gather(
            *[task for _, _, task in tasks],
            return_exceptions=True,
        )

        # Collect successful inferences
        inferred_relationships = []

        for (memory_a_id, memory_b_id, _), result in zip(tasks, results):
            if isinstance(result, Exception):
                logger.warning(
                    f"Inference failed for {memory_a_id[:8]}... <-> {memory_b_id[:8]}...: {result}"
                )
                continue

            if result is not None:  # Valid relationship found
                inferred_relationships.append((memory_a_id, memory_b_id, result))

        logger.info(
            f"Batch inference complete: {len(inferred_relationships)}/{len(memory_pairs)} "
            f"relationships found"
        )

        return inferred_relationships

    async def store_relationship(
        self,
        from_memory_id: str,
        to_memory_id: str,
        inference: RelationshipInference,
    ) -> bool:
        """
        Store inferred relationship in Neo4j.

        Creates a relationship edge with properties:
        - type: LLM-generated relationship type
        - confidence: Confidence score
        - reasoning: Human-readable explanation
        - created_at: Timestamp

        Args:
            from_memory_id: Source memory ID
            to_memory_id: Target memory ID
            inference: Inferred relationship details

        Returns:
            True if stored successfully, False otherwise
        """
        if inference.confidence < self.min_confidence:
            logger.debug(
                f"Skipping relationship storage: confidence {inference.confidence:.2f} "
                f"< threshold {self.min_confidence}"
            )
            return False

        try:
            # Create relationship with LLM-generated type
            query = f"""
            MATCH (from:Memory {{memory_id: $from_id}})
            MATCH (to:Memory {{memory_id: $to_id}})
            CREATE (from)-[r:{inference.relationship_type}]->(to)
            SET r.confidence = $confidence,
                r.reasoning = $reasoning,
                r.created_at = datetime(),
                r.inferred_by = 'llm'
            RETURN r
            """

            async with self.neo4j.driver.session() as session:
                result = await session.run(
                    query,
                    from_id=from_memory_id,
                    to_id=to_memory_id,
                    confidence=inference.confidence,
                    reasoning=inference.reasoning,
                )

                record = await result.single()

                if record:
                    logger.info(
                        f"✓ Relationship stored: {from_memory_id[:8]}... "
                        f"-[{inference.relationship_type}]-> {to_memory_id[:8]}... "
                        f"(confidence: {inference.confidence:.2f})"
                    )
                    return True
                else:
                    logger.warning("Failed to store relationship: Memories not found")
                    return False

        except Exception as e:
            logger.error(f"Failed to store relationship: {e}")
            return False
