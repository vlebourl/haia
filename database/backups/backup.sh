#!/bin/bash
# HAIA Neo4j Backup Script
# Performs database dump using neo4j-admin and maintains 7-day rotation
#
# Usage:
#   ./database/backups/backup.sh [database_name]
#
# Requires:
#   - Docker container 'haia-neo4j' running
#   - Backup volume mounted at /backups in container
#
# Rotation Policy:
#   - Keeps backups for 7 days
#   - Older backups are automatically deleted

set -euo pipefail

# Configuration
CONTAINER_NAME="${CONTAINER_NAME:-haia-neo4j}"
DATABASE_NAME="${1:-neo4j}"
BACKUP_DIR="/backups"
RETENTION_DAYS=7
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="haia_backup_${DATABASE_NAME}_${TIMESTAMP}.dump"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  HAIA Neo4j Backup${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""

# Check if Docker container is running
echo -e "${YELLOW}[1/5]${NC} Checking Neo4j container status..."
if ! docker ps --format '{{.Names}}' | grep -q "^${CONTAINER_NAME}$"; then
    echo -e "${RED}✗ Container '${CONTAINER_NAME}' is not running${NC}"
    exit 1
fi
echo -e "${GREEN}✓ Container is running${NC}"

# Create backup using neo4j-admin dump
echo -e "${YELLOW}[2/5]${NC} Creating database backup..."
if docker exec "${CONTAINER_NAME}" neo4j-admin database dump \
    --to-path="${BACKUP_DIR}" \
    "${DATABASE_NAME}" \
    --overwrite-destination=false \
    > /dev/null 2>&1; then

    # Rename to include timestamp (neo4j-admin creates neo4j.dump by default)
    docker exec "${CONTAINER_NAME}" sh -c "
        if [ -f ${BACKUP_DIR}/${DATABASE_NAME}.dump ]; then
            mv ${BACKUP_DIR}/${DATABASE_NAME}.dump ${BACKUP_DIR}/${BACKUP_FILE}
        fi
    "
    echo -e "${GREEN}✓ Backup created: ${BACKUP_FILE}${NC}"
else
    echo -e "${RED}✗ Backup failed${NC}"
    exit 1
fi

# Get backup file size
BACKUP_SIZE=$(docker exec "${CONTAINER_NAME}" sh -c "du -h ${BACKUP_DIR}/${BACKUP_FILE} | cut -f1" 2>/dev/null || echo "unknown")
echo "  Size: ${BACKUP_SIZE}"

# Verify backup integrity (quick check)
echo -e "${YELLOW}[3/5]${NC} Verifying backup integrity..."
if docker exec "${CONTAINER_NAME}" sh -c "[ -f ${BACKUP_DIR}/${BACKUP_FILE} ] && [ -s ${BACKUP_DIR}/${BACKUP_FILE} ]"; then
    echo -e "${GREEN}✓ Backup file is valid (non-zero size)${NC}"
else
    echo -e "${RED}✗ Backup file is invalid or empty${NC}"
    exit 1
fi

# Rotate old backups (keep last 7 days)
echo -e "${YELLOW}[4/5]${NC} Rotating old backups (keeping ${RETENTION_DAYS} days)..."
DELETED_COUNT=$(docker exec "${CONTAINER_NAME}" sh -c "
    find ${BACKUP_DIR} -name 'haia_backup_*.dump' -type f -mtime +${RETENTION_DAYS} -delete -print | wc -l
" 2>/dev/null || echo "0")

if [ "${DELETED_COUNT}" -gt 0 ]; then
    echo -e "${GREEN}✓ Deleted ${DELETED_COUNT} old backup(s)${NC}"
else
    echo -e "${GREEN}✓ No old backups to delete${NC}"
fi

# List current backups
echo -e "${YELLOW}[5/5]${NC} Current backups:"
docker exec "${CONTAINER_NAME}" sh -c "
    ls -lh ${BACKUP_DIR}/haia_backup_*.dump 2>/dev/null | awk '{print \"  \" \$9 \" (\" \$5 \", \" \$6 \" \" \$7 \")\"}'
" || echo "  No backups found"

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Backup Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo "Backup file: ${BACKUP_FILE}"
echo "Location: Container ${CONTAINER_NAME}:${BACKUP_DIR}/"
echo "Host volume: haia_neo4j-backups"
echo ""
echo "To restore this backup, run:"
echo "  ./database/backups/restore.sh ${BACKUP_FILE}"
echo ""
