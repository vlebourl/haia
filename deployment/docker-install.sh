#!/bin/bash
# HAIA Docker Deployment Script
# One-command deployment for HAIA + Neo4j stack

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  HAIA Docker Stack Deployment${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Step 1: Validate Docker is installed
echo -e "${YELLOW}[1/7]${NC} Checking Docker installation..."
if ! command -v docker &> /dev/null; then
    echo -e "${RED}✗ Docker not found${NC}"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! command -v docker-compose &> /dev/null && ! docker compose version &> /dev/null; then
    echo -e "${RED}✗ Docker Compose not found${NC}"
    echo "Please install Docker Compose: https://docs.docker.com/compose/install/"
    exit 1
fi
echo -e "${GREEN}✓ Docker detected${NC}"

# Determine docker compose command
if docker compose version &> /dev/null; then
    DOCKER_COMPOSE="docker compose"
else
    DOCKER_COMPOSE="docker-compose"
fi

# Step 2: Check for .env file
echo -e "${YELLOW}[2/7]${NC} Validating environment configuration..."
if [ ! -f "${PROJECT_ROOT}/.env" ]; then
    echo -e "${RED}✗ .env file not found${NC}"
    echo "Please copy .env.example to .env and configure it:"
    echo "  cp .env.example .env"
    echo "  nano .env"
    exit 1
fi

# Validate required variables
REQUIRED_VARS=("HAIA_MODEL" "NEO4J_PASSWORD")
MISSING_VARS=()

for VAR in "${REQUIRED_VARS[@]}"; do
    if ! grep -q "^${VAR}=" "${PROJECT_ROOT}/.env"; then
        MISSING_VARS+=("$VAR")
    fi
done

if [ ${#MISSING_VARS[@]} -ne 0 ]; then
    echo -e "${RED}✗ Missing required environment variables:${NC}"
    for VAR in "${MISSING_VARS[@]}"; do
        echo "  - $VAR"
    done
    echo "Please update your .env file"
    exit 1
fi

echo -e "${GREEN}✓ .env file validated${NC}"

# Step 3: Build HAIA container
echo -e "${YELLOW}[3/7]${NC} Building HAIA container image..."
cd "${PROJECT_ROOT}"
$DOCKER_COMPOSE -f deployment/docker-compose.yml --env-file .env build haia
echo -e "${GREEN}✓ HAIA image built${NC}"

# Step 4: Start services
echo -e "${YELLOW}[4/7]${NC} Starting Docker services..."
$DOCKER_COMPOSE -f deployment/docker-compose.yml --env-file .env up -d
echo -e "${GREEN}✓ Services started${NC}"

# Step 5: Wait for Neo4j to be ready
echo -e "${YELLOW}[5/7]${NC} Waiting for Neo4j to be ready..."
MAX_WAIT=60
WAIT_COUNT=0

while [ $WAIT_COUNT -lt $MAX_WAIT ]; do
    if $DOCKER_COMPOSE -f deployment/docker-compose.yml exec -T neo4j cypher-shell -u neo4j -p "$(grep NEO4J_PASSWORD ${PROJECT_ROOT}/.env | cut -d '=' -f2)" "RETURN 1" &> /dev/null; then
        echo -e "${GREEN}✓ Neo4j is ready${NC}"
        break
    fi
    sleep 2
    WAIT_COUNT=$((WAIT_COUNT + 2))
    echo -n "."
done

if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
    echo -e "${RED}✗ Neo4j failed to start within ${MAX_WAIT}s${NC}"
    echo "Check logs: $DOCKER_COMPOSE -f deployment/docker-compose.yml logs neo4j"
    exit 1
fi

# Step 6: Apply Neo4j schema
echo -e "${YELLOW}[6/7]${NC} Applying Neo4j schema..."
if [ -f "${PROJECT_ROOT}/database/schema/init-schema.cypher" ]; then
    docker cp "${PROJECT_ROOT}/database/schema/init-schema.cypher" haia-neo4j:/tmp/init-schema.cypher
    $DOCKER_COMPOSE -f deployment/docker-compose.yml --env-file "${PROJECT_ROOT}/.env" exec -T neo4j cypher-shell -u neo4j -p "$(grep NEO4J_PASSWORD ${PROJECT_ROOT}/.env | cut -d '=' -f2)" < "${PROJECT_ROOT}/database/schema/init-schema.cypher"
    echo -e "${GREEN}✓ Schema applied${NC}"
else
    echo -e "${YELLOW}! Schema file not found (skipping)${NC}"
fi

# Step 7: Health checks
echo -e "${YELLOW}[7/7]${NC} Running health checks..."

# Get HAIA_PORT from .env (default to 8888 if not set)
HAIA_PORT=$(grep -E "^HAIA_PORT=" "${PROJECT_ROOT}/.env" | cut -d '=' -f2 || echo "8888")

# Wait for HAIA to be ready
HAIA_WAIT=0
MAX_HAIA_WAIT=30

while [ $HAIA_WAIT -lt $MAX_HAIA_WAIT ]; do
    if curl -f http://localhost:${HAIA_PORT}/health &> /dev/null; then
        echo -e "${GREEN}✓ HAIA health check passed${NC}"
        break
    fi
    sleep 2
    HAIA_WAIT=$((HAIA_WAIT + 2))
    echo -n "."
done

if [ $HAIA_WAIT -ge $MAX_HAIA_WAIT ]; then
    echo -e "${YELLOW}! HAIA health check timeout (check logs)${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "HAIA API:        ${GREEN}http://localhost:${HAIA_PORT}${NC}"
echo -e "Neo4j Browser:   ${GREEN}http://localhost:7474${NC}"
echo ""
echo "Next steps:"
echo "  1. Test API:        curl http://localhost:${HAIA_PORT}/health"
echo "  2. View logs:       $DOCKER_COMPOSE -f deployment/docker-compose.yml logs -f"
echo "  3. Stop services:   $DOCKER_COMPOSE -f deployment/docker-compose.yml down"
echo ""
