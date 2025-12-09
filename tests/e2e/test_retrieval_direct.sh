#!/bin/bash
# Direct Memory Retrieval Test
# Tests retrieval functionality by creating a memory directly in Neo4j
#
# Prerequisites:
# - Neo4j running at localhost:7687
# - Ollama running at localhost:11434 with nomic-embed-text model
# - HAIA running at localhost:8000
#
# Usage: ./tests/e2e/test_retrieval_direct.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

HAIA_URL="http://localhost:8000"
OLLAMA_URL="http://localhost:11434"
NEO4J_PASSWORD="${NEO4J_PASSWORD:-haia_neo4j_secure_2024}"
TEST_CONVERSATION_ID="test_direct_$(date +%s)"
MEMORY_ID="mem_test_$(date +%s)"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Direct Memory Retrieval Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Step 1: Health checks
echo -e "${BLUE}[1/5] Health Checks${NC}"

echo "Checking HAIA..."
if ! curl -s "${HAIA_URL}/health" > /dev/null; then
    echo -e "${RED}✗ HAIA not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ HAIA is running${NC}"

echo "Checking Ollama..."
if ! curl -s "${OLLAMA_URL}/api/tags" > /dev/null; then
    echo -e "${RED}✗ Ollama not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Ollama is running${NC}"

echo "Checking Neo4j..."
if ! docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" "RETURN 1;" > /dev/null 2>&1; then
    echo -e "${RED}✗ Neo4j not accessible${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Neo4j is accessible${NC}"
echo ""

# Step 2: Generate embedding for test memory
echo -e "${BLUE}[2/5] Generating Test Memory Embedding${NC}"

MEMORY_CONTENT="User strongly prefers Docker over Podman for container orchestration"
echo "Memory content: ${MEMORY_CONTENT}"

# Generate embedding using Ollama
echo "Generating embedding via Ollama..."
embedding_response=$(curl -s -X POST "${OLLAMA_URL}/api/embeddings" \
    -H "Content-Type: application/json" \
    -d "{\"model\": \"nomic-embed-text\", \"prompt\": \"${MEMORY_CONTENT}\"}")

# Extract embedding array
embedding=$(echo "$embedding_response" | jq -c '.embedding')

if [ "$embedding" == "null" ] || [ -z "$embedding" ]; then
    echo -e "${RED}✗ Failed to generate embedding${NC}"
    echo "Response: $embedding_response"
    exit 1
fi

embedding_dim=$(echo "$embedding" | jq 'length')
echo -e "${GREEN}✓ Generated ${embedding_dim}-dimensional embedding${NC}"
echo ""

# Step 3: Insert memory directly into Neo4j
echo -e "${BLUE}[3/5] Inserting Memory into Neo4j${NC}"

# Create Cypher query to insert memory with embedding
cypher_query="CREATE (m:Memory {
    id: '${MEMORY_ID}',
    type: 'preference',
    content: '${MEMORY_CONTENT}',
    confidence: 0.92,
    category: 'containers',
    source_conversation_id: 'test_setup',
    created_at: datetime(),
    has_embedding: true,
    embedding_version: 'nomic-embed-text-v1',
    embedding_updated_at: datetime(),
    embedding: \$embedding_param
})
RETURN m.id as memory_id;"

# Insert memory (using parameter for embedding array)
result=$(docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
    --param "embedding_param=>$embedding" \
    "$cypher_query" 2>&1 | tail -1 | tr -d '"' | tr -d ' ')

if [ "$result" == "${MEMORY_ID}" ]; then
    echo -e "${GREEN}✓ Memory inserted successfully${NC}"
    echo -e "  Memory ID: ${MEMORY_ID}"
else
    echo -e "${RED}✗ Failed to insert memory${NC}"
    echo "Result: $result"
    exit 1
fi

# Verify insertion
verify_result=$(docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
    "MATCH (m:Memory {id: '${MEMORY_ID}'}) RETURN m.has_embedding as has_embedding;" 2>&1 | tail -1 | tr -d ' ')

# Convert to lowercase for comparison (cypher-shell returns TRUE/FALSE in uppercase)
verify_result_lower=$(echo "$verify_result" | tr '[:upper:]' '[:lower:]')

if [ "$verify_result_lower" == "true" ]; then
    echo -e "${GREEN}✓ Memory verified in database with embedding${NC}"
else
    echo -e "${RED}✗ Memory verification failed${NC}"
    echo "Got: '$verify_result'"
    exit 1
fi
echo ""

# Step 4: Test retrieval via conversation
echo -e "${BLUE}[4/5] Testing Memory Retrieval in Conversation${NC}"
echo "Query: What container technology should I use?"
echo ""

response=$(curl -s -X POST "${HAIA_URL}/v1/chat/completions" \
    -H "Content-Type: application/json" \
    -d "{
        \"model\": \"haia\",
        \"messages\": [{\"role\": \"user\", \"content\": \"What container technology should I use for my homelab?\"}],
        \"conversation_id\": \"${TEST_CONVERSATION_ID}\",
        \"user_id\": \"test_user_direct\"
    }")

assistant_response=$(echo "$response" | jq -r '.choices[0].message.content // empty')

if [ -z "$assistant_response" ]; then
    echo -e "${RED}✗ API call failed${NC}"
    echo "Response: $response"
    exit 1
fi

echo -e "${GREEN}Assistant Response:${NC}"
echo "$assistant_response"
echo ""

# Step 5: Verify memory was retrieved
echo -e "${BLUE}[5/5] Verification${NC}"

# Check if response mentions Docker (indicates memory was likely used)
if echo "$assistant_response" | grep -qi "docker"; then
    echo -e "${GREEN}✓ Response mentions Docker${NC}"

    # Check for contextual awareness indicators
    if echo "$assistant_response" | grep -qiE "prefer|mentioned|previous|based on|know that|recall|remember"; then
        echo -e "${GREEN}✓ Response shows contextual awareness!${NC}"
        echo -e "${GREEN}  MEMORY RETRIEVAL WORKING CORRECTLY!${NC}"
    else
        echo -e "${YELLOW}⚠ Response mentions Docker but doesn't clearly show memory usage${NC}"
        echo -e "${YELLOW}  (This could be coincidental - LLM may suggest Docker anyway)${NC}"
    fi
else
    echo -e "${RED}✗ Response doesn't mention Docker${NC}"
    echo -e "${YELLOW}  Possible causes:${NC}"
    echo -e "${YELLOW}  - Retrieval service not working${NC}"
    echo -e "${YELLOW}  - Query-memory similarity too low${NC}"
    echo -e "${YELLOW}  - Ollama embedding service issue${NC}"
fi

echo ""

# Cleanup
echo -e "${BLUE}Cleanup${NC}"
echo "Removing test memory..."
docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD}" \
    "MATCH (m:Memory {id: '${MEMORY_ID}'}) DELETE m;" > /dev/null 2>&1
echo -e "${GREEN}✓ Test memory removed${NC}"

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${GREEN}Test Complete!${NC}"
echo -e "${BLUE}========================================${NC}"
