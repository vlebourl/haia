// Schema Verification Queries for HAIA Memory System
// Run this file to verify Neo4j schema is correctly applied
//
// Usage:
//   docker exec -i haia-neo4j cypher-shell -u neo4j -p <password> < database/schema/verify-schema.cypher

// ========================================
// 1. Check Schema Version
// ========================================
MATCH (sv:SchemaVersion)
RETURN sv.version AS schema_version,
       sv.applied_at AS applied_at;

// ========================================
// 2. Verify All Constraints Exist
// ========================================
SHOW CONSTRAINTS;

// Expected constraints:
// - person_user_id (UNIQUE on Person.user_id)
// - interest_id (UNIQUE on Interest.interest_id)
// - infrastructure_id (UNIQUE on Infrastructure.infra_id)
// - tech_pref_id (UNIQUE on TechPreference.pref_id)
// - fact_id (UNIQUE on Fact.fact_id)
// - decision_id (UNIQUE on Decision.decision_id)
// - conversation_id (UNIQUE on Conversation.conversation_id)

// ========================================
// 3. Verify All Indexes Exist
// ========================================
SHOW INDEXES;

// Expected indexes (auto-created from UNIQUE constraints):
// - person_user_id_index
// - interest_id_index
// - infrastructure_id_index
// - tech_pref_id_index
// - fact_id_index
// - decision_id_index
// - conversation_id_index

// ========================================
// 4. Count Nodes by Type
// ========================================
MATCH (n)
RETURN labels(n) AS node_type, count(n) AS count
ORDER BY node_type;

// ========================================
// 5. Count Relationships by Type
// ========================================
MATCH ()-[r]->()
RETURN type(r) AS relationship_type, count(r) AS count
ORDER BY relationship_type;

// ========================================
// 6. Verify SchemaVersion Node Exists
// ========================================
MATCH (sv:SchemaVersion)
RETURN
  CASE
    WHEN count(sv) = 1 THEN 'PASS: Schema version node exists'
    ELSE 'FAIL: Schema version node missing or duplicate'
  END AS result;

// ========================================
// 7. Test Constraint Enforcement
// ========================================

// Test Person uniqueness (should succeed)
MERGE (p:Person {user_id: "test_person_001"})
SET p.name = "Test Person", p.created_at = datetime()
RETURN "PASS: Person creation succeeded" AS result;

// Test Interest uniqueness (should succeed)
MERGE (i:Interest {interest_id: "test_interest_001"})
SET i.name = "Test Interest",
    i.confidence = 0.5,
    i.created_at = datetime()
RETURN "PASS: Interest creation succeeded" AS result;

// Clean up test nodes
MATCH (n) WHERE n.user_id = "test_person_001" OR n.interest_id = "test_interest_001"
DETACH DELETE n
RETURN "PASS: Test cleanup completed" AS result;

// ========================================
// 8. Verify Schema is Ready for Use
// ========================================
MATCH (sv:SchemaVersion)
WITH sv,
     count{MATCH (p:Person)} AS person_count,
     count{MATCH (i:Interest)} AS interest_count
RETURN
  sv.version AS version,
  CASE
    WHEN sv.version IS NOT NULL THEN 'PASS: Schema initialized'
    ELSE 'FAIL: Schema not initialized'
  END AS status,
  person_count AS persons,
  interest_count AS interests;

// ========================================
// End of Verification
// ========================================
// If all queries ran successfully, the schema is correctly applied!
