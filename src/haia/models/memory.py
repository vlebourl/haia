"""Pydantic models for Neo4j memory graph entities.

This module defines type-safe models for all memory node types stored in Neo4j.
Each model corresponds to a node type in the graph schema.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


def generate_node_id(prefix: str) -> str:
    """Generate a unique node ID with prefix.

    Args:
        prefix: Node type prefix (e.g., 'person', 'interest', 'fact')

    Returns:
        Unique ID string in format: {prefix}_{uuid12}

    Example:
        >>> generate_node_id("person")
        'person_a3f2c1b4d5e6'
    """
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class PersonNode(BaseModel):
    """Person node representing the user.

    Properties align with Neo4j schema defined in contracts/neo4j-schema.cypher.
    """

    user_id: str = Field(default_factory=lambda: generate_node_id("person"))
    name: str
    timezone: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class InterestNode(BaseModel):
    """Interest node for topics the user cares about.

    Properties align with Neo4j schema defined in contracts/neo4j-schema.cypher.
    """

    interest_id: str = Field(default_factory=lambda: generate_node_id("interest"))
    name: str
    category: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class InfrastructureNode(BaseModel):
    """Infrastructure node for homelab components.

    Properties align with Neo4j schema defined in contracts/neo4j-schema.cypher.
    """

    infra_id: str = Field(default_factory=lambda: generate_node_id("infra"))
    name: str
    type: str  # proxmox, homeassistant, docker, service, etc.
    hostname: Optional[str] = None
    criticality: Literal["low", "medium", "high", "critical"]
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class TechPreferenceNode(BaseModel):
    """Technical preference node for technology stack choices.

    Properties align with Neo4j schema defined in contracts/neo4j-schema.cypher.
    """

    pref_id: str = Field(default_factory=lambda: generate_node_id("pref"))
    technology: str
    preference_type: Literal["likes", "dislikes", "avoids", "prefers"]
    rationale: Optional[str] = None
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class FactNode(BaseModel):
    """Fact node for general knowledge about the user.

    Properties align with Neo4j schema defined in contracts/neo4j-schema.cypher.
    """

    fact_id: str = Field(default_factory=lambda: generate_node_id("fact"))
    content: str
    fact_type: Literal["personal", "technical", "contextual"]
    confidence: float = Field(ge=0.0, le=1.0)
    source_conversation_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class DecisionNode(BaseModel):
    """Decision node for past decisions with context.

    Properties align with Neo4j schema defined in contracts/neo4j-schema.cypher.
    """

    decision_id: str = Field(default_factory=lambda: generate_node_id("decision"))
    decision: str
    context: Optional[str] = None
    rationale: Optional[str] = None
    date_made: Optional[date] = None
    confidence: float = Field(ge=0.0, le=1.0)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None


class ConversationNode(BaseModel):
    """Conversation metadata node for extraction tracking.

    Properties align with Neo4j schema defined in contracts/neo4j-schema.cypher.
    """

    conversation_id: str = Field(default_factory=lambda: generate_node_id("conv"))
    started_at: datetime
    ended_at: Optional[datetime] = None
    message_count: int = Field(ge=0)
    summary: Optional[str] = None
    topics: Optional[list[str]] = None
