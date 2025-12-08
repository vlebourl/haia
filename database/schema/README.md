# Neo4j Graph Schema: HAIA Memory System

**Version**: 1.0
**Last Updated**: 2025-12-08
**Database**: Neo4j 5.15

## Overview

This document defines the complete graph schema for HAIA's personal memory system. The schema is designed to store and relate various types of memories extracted from conversations with Vincent, including interests, infrastructure components, technical preferences, facts, and decisions.

## Schema Initialization

The schema is automatically applied during deployment via `init-schema.cypher`. To manually apply:

```bash
# Via deployment script
./deployment/docker-install.sh

# Or manually
docker exec -i haia-neo4j cypher-shell -u neo4j -p <password> < database/schema/init-schema.cypher
```

## Node Types

### 1. Person

Represents the user (Vincent).

**Properties**:
- `user_id`: String (UNIQUE, required) - Identifier for the user
- `name`: String (required) - User's name
- `timezone`: String (optional) - User's timezone
- `created_at`: DateTime (required) - Node creation timestamp
- `updated_at`: DateTime (optional) - Last modification timestamp

**Constraints**:
- UNIQUE constraint on `user_id`
- NOT NULL on `user_id`, `name`, `created_at`

### 2. Interest

Topics, hobbies, or areas the user cares about.

**Properties**:
- `interest_id`: String (UNIQUE, required) - Format: `interest_{uuid12}`
- `name`: String (required) - Interest name
- `category`: String (optional) - Category grouping
- `confidence`: Float (required) - Confidence score 0.0-1.0
- `created_at`: DateTime (required)
- `updated_at`: DateTime (optional)

**Constraints**:
- UNIQUE constraint on `interest_id`
- NOT NULL on `interest_id`, `name`, `confidence`, `created_at`

### 3. Infrastructure

Homelab infrastructure components (servers, services, devices).

**Properties**:
- `infra_id`: String (UNIQUE, required) - Format: `infra_{uuid12}`
- `name`: String (required) - Component name
- `type`: String (required) - Type (proxmox, homeassistant, docker, service)
- `hostname`: String (optional) - Network hostname or IP
- `criticality`: String (required) - Level: low, medium, high, critical
- `created_at`: DateTime (required)
- `updated_at`: DateTime (optional)

**Constraints**:
- UNIQUE constraint on `infra_id`
- NOT NULL on `infra_id`, `name`, `type`, `criticality`, `created_at`

### 4. TechPreference

Technical preferences, likes/dislikes, technology stack choices.

**Properties**:
- `pref_id`: String (UNIQUE, required) - Format: `pref_{uuid12}`
- `technology`: String (required) - Technology name
- `preference_type`: String (required) - Type: likes, dislikes, avoids, prefers
- `rationale`: String (optional) - Why this preference exists
- `confidence`: Float (required) - Confidence score 0.0-1.0
- `created_at`: DateTime (required)
- `updated_at`: DateTime (optional)

**Constraints**:
- UNIQUE constraint on `pref_id`
- NOT NULL on `pref_id`, `technology`, `preference_type`, `confidence`, `created_at`

### 5. Fact

General facts about the user, their environment, or context.

**Properties**:
- `fact_id`: String (UNIQUE, required) - Format: `fact_{uuid12}`
- `content`: String (required) - The fact content
- `fact_type`: String (required) - Type: personal, technical, contextual
- `confidence`: Float (required) - Confidence score 0.0-1.0
- `source_conversation_id`: String (optional) - Reference to source conversation
- `created_at`: DateTime (required)
- `updated_at`: DateTime (optional)

**Constraints**:
- UNIQUE constraint on `fact_id`
- NOT NULL on `fact_id`, `content`, `fact_type`, `confidence`, `created_at`

### 6. Decision

Past decisions made by the user with context and rationale.

**Properties**:
- `decision_id`: String (UNIQUE, required) - Format: `decision_{uuid12}`
- `topic`: String (required) - Decision topic or area
- `chosen_option`: String (required) - What was decided
- `alternative_options`: String (optional) - What was rejected
- `rationale`: String (optional) - Why this decision was made
- `confidence`: Float (required) - Confidence score 0.0-1.0
- `source_conversation_id`: String (optional) - Reference to source conversation
- `created_at`: DateTime (required)
- `updated_at`: DateTime (optional)

**Constraints**:
- UNIQUE constraint on `decision_id`
- NOT NULL on `decision_id`, `topic`, `chosen_option`, `confidence`, `created_at`

### 7. Conversation

Represents a conversation boundary for memory extraction.

**Properties**:
- `conversation_id`: String (UNIQUE, required) - Format: `conv_{uuid12}`
- `started_at`: DateTime (required) - Conversation start time
- `ended_at`: DateTime (optional) - Conversation end time
- `message_count`: Integer (optional) - Number of messages in conversation
- `created_at`: DateTime (required)

**Constraints**:
- UNIQUE constraint on `conversation_id`
- NOT NULL on `conversation_id`, `started_at`, `created_at`

## Relationships

### User Relationships

- `(:Person)-[:INTERESTED_IN]->(:Interest)` - User's interests
- `(:Person)-[:OWNS]->(:Infrastructure)` - User's infrastructure
- `(:Person)-[:PREFERS]->(:TechPreference)` - User's tech preferences
- `(:Person)-[:HAS_FACT]->(:Fact)` - Facts about the user
- `(:Person)-[:MADE_DECISION]->(:Decision)` - User's decisions

### Conversation Relationships

- `(:Conversation)-[:CONTAINS]->(:Message)` - Messages in a conversation (future)
- `(:Conversation)-[:EXTRACTED]->(:Interest)` - Interests extracted from conversation
- `(:Conversation)-[:EXTRACTED]->(:Fact)` - Facts extracted from conversation
- `(:Conversation)-[:EXTRACTED]->(:Decision)` - Decisions extracted from conversation

### Cross-Entity Relationships

- `(:Interest)-[:RELATED_TO]->(:Interest)` - Related interests
- `(:Infrastructure)-[:DEPENDS_ON]->(:Infrastructure)` - Infrastructure dependencies
- `(:Decision)-[:SUPERSEDES]->(:Decision)` - Later decision overrides earlier one

## Indexes

Performance indexes are automatically created:

- `person_user_id_index` on Person.user_id (UNIQUE)
- `interest_id_index` on Interest.interest_id (UNIQUE)
- `infrastructure_id_index` on Infrastructure.infra_id (UNIQUE)
- `tech_pref_id_index` on TechPreference.pref_id (UNIQUE)
- `fact_id_index` on Fact.fact_id (UNIQUE)
- `decision_id_index` on Decision.decision_id (UNIQUE)
- `conversation_id_index` on Conversation.conversation_id (UNIQUE)

## Schema Verification

To verify the schema is correctly applied:

```bash
# Check constraints
docker exec haia-neo4j cypher-shell -u neo4j -p <password> "SHOW CONSTRAINTS"

# Check indexes
docker exec haia-neo4j cypher-shell -u neo4j -p <password> "SHOW INDEXES"

# Count nodes by type
docker exec haia-neo4j cypher-shell -u neo4j -p <password> "
  MATCH (n)
  RETURN labels(n) AS type, count(n) AS count
  ORDER BY type
"
```

Or use the verification script:

```bash
docker exec -i haia-neo4j cypher-shell -u neo4j -p <password> < database/schema/verify-schema.cypher
```

## Usage Examples

### Create a Person node

```cypher
CREATE (p:Person {
  user_id: "person_vincent001",
  name: "Vincent",
  timezone: "Europe/Brussels",
  created_at: datetime()
})
RETURN p
```

### Create an Interest and link to Person

```cypher
MATCH (p:Person {user_id: "person_vincent001"})
CREATE (i:Interest {
  interest_id: "interest_" + randomUUID()[0..11],
  name: "whisky tasting",
  category: "beverages",
  confidence: 0.95,
  created_at: datetime()
})
CREATE (p)-[:INTERESTED_IN]->(i)
RETURN i
```

### Query all interests for a user

```cypher
MATCH (p:Person {user_id: "person_vincent001"})-[:INTERESTED_IN]->(i:Interest)
RETURN i.name AS interest, i.category AS category, i.confidence AS confidence
ORDER BY i.confidence DESC
```

## Schema Versioning

The schema includes a SchemaVersion node to track migrations:

```cypher
MATCH (sv:SchemaVersion)
RETURN sv.version AS version, sv.applied_at AS applied_at
```

Current version: **1.0.0** (Initial schema for Session 6)

## Future Extensions

Planned for future sessions (4-6):

- **Message** nodes for complete conversation history
- **Topic** nodes for conversation topic clustering
- **Embedding** vectors for semantic search
- **Event** nodes for temporal memory timeline
- Additional relationship types for rich context

## See Also

- Schema definition: `database/schema/init-schema.cypher`
- Schema verification: `database/schema/verify-schema.cypher`
- Data model documentation: `specs/006-docker-neo4j-stack/data-model.md`
- Python models: `src/haia/models/memory.py`
