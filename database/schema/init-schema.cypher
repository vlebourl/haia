// Neo4j Memory Graph Schema Initialization
// Feature: Docker Compose Stack with Neo4j Memory Database
// Version: 1.0.0
// Date: 2025-12-07

// ==============================================================================
// CONSTRAINTS (Uniqueness)
// ==============================================================================

// Person node constraints
CREATE CONSTRAINT person_user_id IF NOT EXISTS
FOR (p:Person)
REQUIRE p.user_id IS UNIQUE;

// Interest node constraints
CREATE CONSTRAINT interest_id IF NOT EXISTS
FOR (i:Interest)
REQUIRE i.interest_id IS UNIQUE;

// Infrastructure node constraints
CREATE CONSTRAINT infrastructure_id IF NOT EXISTS
FOR (inf:Infrastructure)
REQUIRE inf.infra_id IS UNIQUE;

// TechPreference node constraints
CREATE CONSTRAINT tech_pref_id IF NOT EXISTS
FOR (tp:TechPreference)
REQUIRE tp.pref_id IS UNIQUE;

// Fact node constraints
CREATE CONSTRAINT fact_id IF NOT EXISTS
FOR (f:Fact)
REQUIRE f.fact_id IS UNIQUE;

// Decision node constraints
CREATE CONSTRAINT decision_id IF NOT EXISTS
FOR (d:Decision)
REQUIRE d.decision_id IS UNIQUE;

// Conversation node constraints
CREATE CONSTRAINT conversation_id IF NOT EXISTS
FOR (c:Conversation)
REQUIRE c.conversation_id IS UNIQUE;

// ==============================================================================
// INDEXES (Performance)
// ==============================================================================

// Person indexes
CREATE INDEX person_created IF NOT EXISTS
FOR (p:Person)
ON (p.created_at);

// Interest indexes
CREATE INDEX interest_confidence IF NOT EXISTS
FOR (i:Interest)
ON (i.confidence);

CREATE INDEX interest_category IF NOT EXISTS
FOR (i:Interest)
ON (i.category);

CREATE INDEX interest_created IF NOT EXISTS
FOR (i:Interest)
ON (i.created_at);

// Infrastructure indexes
CREATE INDEX infrastructure_type IF NOT EXISTS
FOR (inf:Infrastructure)
ON (inf.type);

CREATE INDEX infrastructure_criticality IF NOT EXISTS
FOR (inf:Infrastructure)
ON (inf.criticality);

CREATE INDEX infrastructure_created IF NOT EXISTS
FOR (inf:Infrastructure)
ON (inf.created_at);

// TechPreference indexes
CREATE INDEX tech_pref_type IF NOT EXISTS
FOR (tp:TechPreference)
ON (tp.preference_type);

CREATE INDEX tech_pref_confidence IF NOT EXISTS
FOR (tp:TechPreference)
ON (tp.confidence);

CREATE INDEX tech_pref_created IF NOT EXISTS
FOR (tp:TechPreference)
ON (tp.created_at);

// Fact indexes
CREATE INDEX fact_created IF NOT EXISTS
FOR (f:Fact)
ON (f.created_at);

CREATE INDEX fact_confidence IF NOT EXISTS
FOR (f:Fact)
ON (f.confidence);

CREATE INDEX fact_type IF NOT EXISTS
FOR (f:Fact)
ON (f.fact_type);

// Decision indexes
CREATE INDEX decision_date IF NOT EXISTS
FOR (d:Decision)
ON (d.date_made);

CREATE INDEX decision_confidence IF NOT EXISTS
FOR (d:Decision)
ON (d.confidence);

CREATE INDEX decision_created IF NOT EXISTS
FOR (d:Decision)
ON (d.created_at);

// Conversation indexes
CREATE INDEX conversation_started IF NOT EXISTS
FOR (c:Conversation)
ON (c.started_at);

CREATE INDEX conversation_ended IF NOT EXISTS
FOR (c:Conversation)
ON (c.ended_at);

// ==============================================================================
// SCHEMA METADATA
// ==============================================================================

// Create schema version tracking node
CREATE (v:SchemaVersion {
  version: "1.0.0",
  applied_at: datetime(),
  description: "Initial memory graph schema with 7 node types (Person, Interest, Infrastructure, TechPreference, Fact, Decision, Conversation)",
  session: "006-docker-neo4j-stack"
});
