#!/bin/bash
# HAIA Neo4j Restore Script
# Restores database from a backup dump file
#
# Usage:
#   ./database/backups/restore.sh <backup_file>
#
# Example:
#   ./database/backups/restore.sh haia_backup_neo4j_20251208_120000.dump
#
# WARNING: This will REPLACE the current database with the backup data!
#          All current data will be lost. Make sure you have a recent backup before proceeding.

set -euo pipefail

# Configuration
CONTAINER_NAME="${CONTAINER_NAME:-haia-neo4j}"
DATABASE_NAME="${DATABASE_NAME:-neo4j}"
BACKUP_DIR="/backups"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}Error: Backup file name required${NC}"
    echo ""
    echo "Usage: $0 <backup_file>"
    echo ""
    echo "Available backups:"
    docker exec "${CONTAINER_NAME}" sh -c "ls -1 ${BACKUP_DIR}/haia_backup_*.dump 2>/dev/null" || echo "  No backups found"
    exit 1
fi

BACKUP_FILE="$1"
BACKUP_PATH="${BACKUP_DIR}/${BACKUP_FILE}"

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  HAIA Neo4j Database Restore${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Check if Docker container is running
echo -e "${YELLOW}[1/7]${NC} Checking Neo4j container status..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}✗ Container '${CONTAINER_NAME}' is not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Container is running${NC}"

# Verify backup file exists
echo -e "${YELLOW}[2/7]${NC} Verifying backup file..."
if ! docker exec "${CONTAINER_NAME}" sh -c "[ -f ${BACKUP_PATH} ]"; then
    echo -e "${RED}✗ Backup file not found: ${BACKUP_FILE}${NC}"
    echo ""
    echo "Available backups:"
    docker exec "${CONTAINER_NAME}" sh -c "ls -1 ${BACKUP_DIR}/haia_backup_*.dump 2>/dev/null" || echo "  No backups found"
    exit 1
fi

BACKUP_SIZE=$(docker exec "${CONTAINER_NAME}" sh -c "du -h ${BACKUP_PATH} | cut -f1")
echo -e "${GREEN}✓ Backup file found: ${BACKUP_FILE} (${BACKUP_SIZE})${NC}"

# Confirmation prompt
echo ""
echo -e "${RED}WARNING: This will REPLACE the current database!${NC}"
echo -e "${RED}         All current data will be LOST!${NC}"
echo ""
read -p "Are you sure you want to restore from this backup? (yes/no): " -r
echo ""
if [[ ! $REPLY =~ ^[Yy][Ee][Ss]$ ]]; then
    echo "Restore cancelled."
    exit 0
fi

# Create a current backup before restore (safety measure)
echo -e "${YELLOW}[3/7]${NC} Creating safety backup of current database..."
SAFETY_BACKUP="haia_backup_${DATABASE_NAME}_pre_restore_$(date +%Y%m%d_%H%M%S).dump"
if docker exec "${CONTAINER_NAME}" neo4j-admin database dump \
    --to-path="${BACKUP_DIR}" \
    "${DATABASE_NAME}" \
    --overwrite-destination=false \
    > /dev/null 2>&1; then

    docker exec "${CONTAINER_NAME}" sh -c "
        if [ -f ${BACKUP_DIR}/${DATABASE_NAME}.dump ]; then
            mv ${BACKUP_DIR}/${DATABASE_NAME}.dump ${BACKUP_DIR}/${SAFETY_BACKUP}
        fi
    "
    echo -e "${GREEN}✓ Safety backup created: ${SAFETY_BACKUP}${NC}"
else
    echo -e "${YELLOW}⚠ Could not create safety backup (continuing anyway)${NC}"
fi

# Stop the database
echo -e "${YELLOW}[4/7]${NC} Stopping database..."
if docker exec "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
    "STOP DATABASE ${DATABASE_NAME}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Database stopped${NC}"
    sleep 2
else
    echo -e "${YELLOW}⚠ Database may already be stopped${NC}"
fi

# Load the backup
echo -e "${YELLOW}[5/7]${NC} Restoring database from backup..."
if docker exec "${CONTAINER_NAME}" neo4j-admin database load \
    --from-path="${BACKUP_DIR}" \
    "${DATABASE_NAME}" \
    --overwrite-destination=true \
    > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Database restored from backup${NC}"
else
    echo -e "${RED}✗ Restore failed${NC}"
    echo "Attempting to restart database..."
    docker exec "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
        "START DATABASE ${DATABASE_NAME}" > /dev/null 2>&1 || true
    exit 1
fi

# Start the database
echo -e "${YELLOW}[6/7]${NC} Starting database..."
if docker exec "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
    "START DATABASE ${DATABASE_NAME}" > /dev/null 2>&1; then
    echo -e "${GREEN}✓ Database started${NC}"
    sleep 3
else
    echo -e "${YELLOW}⚠ Database may have auto-started${NC}"
fi

# Verify restore by querying database
echo -e "${YELLOW}[7/7]${NC} Verifying restored database..."
sleep 2
if docker exec "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
    "MATCH (n) RETURN count(n) AS total_nodes" > /dev/null 2>&1; then

    NODE_COUNT=$(docker exec "${CONTAINER_NAME}" cypher-shell -u neo4j -p "${NEO4J_PASSWORD:-password}" \
        "MATCH (n) RETURN count(n) AS total_nodes" 2>/dev/null | grep -oP '\d+' | head -1 || echo "0")

    echo -e "${GREEN}✓ Database is accessible${NC}"
    echo "  Total nodes in restored database: ${NODE_COUNT}"
else
    echo -e "${RED}✗ Database verification failed${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Restore Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Database '${DATABASE_NAME}' has been restored from:"
echo "  ${BACKUP_FILE}"
echo ""
echo "Safety backup created:"
echo "  ${SAFETY_BACKUP}"
echo ""
