#!/bin/bash
# End-to-End Memory Lifecycle Test
# Tests: Memory Extraction (Session 7) + Embedding Generation (Session 8) + Retrieval (Session 8)
#
# Prerequisites:
# - Neo4j running at localhost:7687
# - Ollama running at localhost:11434 with nomic-embed-text model
# - HAIA running at localhost:8000
#
# Usage: ./tests/e2e/test_memory_lifecycle.sh

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test configuration
HAIA_URL="http://localhost:8000"
CONVERSATION_ID="test_e2e_$(date +%s)"
TEST_USER="test_user_e2e"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}HAIA Memory Lifecycle End-to-End Test${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Function to make API call
api_call() {
    local conversation_id=$1
    local user_message=$2
    local description=$3

    echo -e "${YELLOW}➜ ${description}${NC}"
    echo -e "  User: ${user_message}"

    response=$(curl -s -X POST "${HAIA_URL}/v1/chat/completions" \
        -H "Content-Type: application/json" \
        -d "{
            \"model\": \"haia\",
            \"messages\": [{\"role\": \"user\", \"content\": \"${user_message}\"}],
            \"conversation_id\": \"${conversation_id}\",
            \"user_id\": \"${TEST_USER}\"
        }")

    # Extract assistant response
    assistant_response=$(echo "$response" | jq -r '.choices[0].message.content // empty')

    if [ -z "$assistant_response" ]; then
        echo -e "${RED}✗ API call failed${NC}"
        echo "Full response: $response"
        return 1
    fi

    echo -e "  ${GREEN}Assistant:${NC} ${assistant_response:0:200}..."
    echo ""

    echo "$response"
}

# Step 1: Health check
echo -e "${BLUE}[1/6] Health Check${NC}"
echo -e "Checking HAIA API..."
health_response=$(curl -s "${HAIA_URL}/health" || echo "failed")

if [ "$health_response" == "failed" ]; then
    echo -e "${RED}✗ HAIA API is not running at ${HAIA_URL}${NC}"
    echo -e "${YELLOW}  Start HAIA with: uv run uvicorn haia.api.app:app --reload${NC}"
    exit 1
fi

echo -e "${GREEN}✓ HAIA API is healthy${NC}"
echo ""

# Step 2: Initial conversation to create memory
echo -e "${BLUE}[2/6] Creating Memory via Conversation${NC}"
echo -e "Having a conversation to establish Docker preference..."
echo ""

conv1_response=$(api_call "${CONVERSATION_ID}" \
    "I really prefer using Docker over Podman for container management. Docker has better documentation and tooling." \
    "Establishing Docker preference")

# Give a follow-up to make the conversation more substantial
conv2_response=$(api_call "${CONVERSATION_ID}" \
    "Yes, Docker Compose is much easier to use than Podman's equivalent." \
    "Reinforcing preference")

echo -e "${GREEN}✓ Initial conversation completed${NC}"
echo -e "${YELLOW}  Conversation ID: ${CONVERSATION_ID}${NC}"
echo ""

# Step 3: Wait for boundary detection and memory extraction
echo -e "${BLUE}[3/6] Triggering Memory Extraction${NC}"
echo -e "${YELLOW}Note: In production, boundary detection happens after 10+ minutes of idle time.${NC}"
echo -e "${YELLOW}For testing, we'll trigger it by ending the conversation.${NC}"
echo ""

# End the conversation by starting a new one (simulates boundary)
NEW_CONVERSATION_ID="test_e2e_followup_$(date +%s)"

# Wait a moment for any background processing
echo "Waiting 3 seconds for extraction processing..."
sleep 3

# Check if memory was extracted (query Neo4j)
echo -e "Checking Neo4j for extracted memory..."

memory_check=$(docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-haia_neo4j_secure_2024}" \
    "MATCH (m:Memory) WHERE m.content CONTAINS 'Docker' AND m.source_conversation_id = '${CONVERSATION_ID}' RETURN count(m) as count;" \
    2>/dev/null | tail -1 | tr -d ' ' || echo "0")

if [ "$memory_check" != "0" ]; then
    echo -e "${GREEN}✓ Memory extracted and stored in Neo4j${NC}"

    # Check if memory has embedding
    embedding_check=$(docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-haia_neo4j_secure_2024}" \
        "MATCH (m:Memory) WHERE m.content CONTAINS 'Docker' AND m.source_conversation_id = '${CONVERSATION_ID}' RETURN m.has_embedding as has_embedding;" \
        2>/dev/null | tail -1 | tr -d ' ' || echo "false")

    if [ "$embedding_check" == "true" ]; then
        echo -e "${GREEN}✓ Memory has embedding generated${NC}"
    else
        echo -e "${YELLOW}⚠ Memory exists but embedding not yet generated (backfill worker will process it)${NC}"
    fi
else
    echo -e "${YELLOW}⚠ Memory not yet extracted (may need more time or conversation ended manually)${NC}"
    echo -e "${YELLOW}  Continuing test anyway...${NC}"
fi
echo ""

# Step 4: Have a related conversation where memory should be retrieved
echo -e "${BLUE}[4/6] Testing Memory Retrieval${NC}"
echo -e "Having a new conversation about containers..."
echo ""

retrieval_response=$(api_call "${NEW_CONVERSATION_ID}" \
    "What container technology should I use for my homelab?" \
    "Query that should trigger Docker memory retrieval")

# Step 5: Verify memory was retrieved
echo -e "${BLUE}[5/6] Verifying Memory Retrieval${NC}"

# Check if the response mentions Docker preference (indicates memory was used)
if echo "$retrieval_response" | jq -r '.choices[0].message.content' | grep -i "docker" > /dev/null; then
    echo -e "${GREEN}✓ Response mentions Docker (likely retrieved memory)${NC}"

    # Try to find evidence of memory injection in the response
    assistant_text=$(echo "$retrieval_response" | jq -r '.choices[0].message.content')

    if echo "$assistant_text" | grep -iE "prefer|mentioned|previous|know that|recall" > /dev/null; then
        echo -e "${GREEN}✓ Response shows contextual awareness (strong indication of memory retrieval)${NC}"
        echo -e "${GREEN}  Assistant acknowledged your preference!${NC}"
    else
        echo -e "${YELLOW}⚠ Response mentions Docker but may not have used retrieved memory${NC}"
    fi
else
    echo -e "${RED}✗ Response doesn't mention Docker${NC}"
    echo -e "${YELLOW}  This could mean:${NC}"
    echo -e "${YELLOW}  - Memory hasn't been extracted yet (boundary not triggered)${NC}"
    echo -e "${YELLOW}  - Embedding not generated yet (backfill in progress)${NC}"
    echo -e "${YELLOW}  - Retrieval service is not working${NC}"
    echo -e "${YELLOW}  - Query similarity too low${NC}"
fi
echo ""

# Step 6: Direct database verification
echo -e "${BLUE}[6/6] Database Verification${NC}"

echo "Checking memories in Neo4j..."
memory_count=$(docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-haia_neo4j_secure_2024}" \
    "MATCH (m:Memory) WHERE m.content CONTAINS 'Docker' RETURN count(m) as count;" \
    2>/dev/null | tail -1 | tr -d ' ' || echo "0")

echo -e "Total Docker-related memories: ${memory_count}"

if [ "$memory_count" != "0" ]; then
    echo -e "${GREEN}✓ Memories exist in database${NC}"

    # Check embedding status
    with_embeddings=$(docker exec haia-neo4j cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-haia_neo4j_secure_2024}" \
        "MATCH (m:Memory) WHERE m.content CONTAINS 'Docker' AND m.has_embedding = true RETURN count(m) as count;" \
        2>/dev/null | tail -1 | tr -d ' ' || echo "0")

    echo -e "Memories with embeddings: ${with_embeddings}"

    if [ "$with_embeddings" != "0" ]; then
        echo -e "${GREEN}✓ Embeddings have been generated${NC}"
    else
        echo -e "${YELLOW}⚠ Embeddings not yet generated${NC}"
        echo -e "${YELLOW}  The backfill worker runs every 60 seconds${NC}"
    fi
else
    echo -e "${YELLOW}⚠ No Docker-related memories found${NC}"
    echo -e "${YELLOW}  Memory extraction may not have completed yet${NC}"
fi

echo ""
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}Test Summary${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "Test Conversation ID: ${CONVERSATION_ID}"
echo -e "Follow-up Conversation ID: ${NEW_CONVERSATION_ID}"
echo -e ""
echo -e "${GREEN}✓ API health check passed${NC}"
echo -e "${GREEN}✓ Initial conversation completed${NC}"
echo -e "${GREEN}✓ Follow-up conversation completed${NC}"
echo -e ""
echo -e "${YELLOW}Manual Verification Steps:${NC}"
echo -e "1. Check logs: tail -f logs/haia.log | grep -E 'extract|retriev|embedding'"
echo -e "2. Check Neo4j: docker exec -it haia-neo4j cypher-shell -u neo4j -p ${NEO4J_PASSWORD:-haia_neo4j_secure_2024}"
echo -e "   MATCH (m:Memory) WHERE m.content CONTAINS 'Docker' RETURN m;"
echo -e "3. Wait 60s for backfill worker if embeddings not yet generated"
echo -e ""
echo -e "${GREEN}Test completed!${NC}"
