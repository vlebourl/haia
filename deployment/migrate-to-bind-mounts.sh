#!/bin/bash
# Migration script: Move data from Docker named volumes to bind mounts
# This script safely migrates existing data to the new portable data/ directory

set -e

echo "HAIA Data Migration to Bind Mounts"
echo "===================================="
echo ""

# Configuration
DATA_DIR="${DATA_DIR:-../data}"
cd "$(dirname "$0")"

echo "Target directory: $DATA_DIR"
echo ""

# Stop containers
echo "1. Stopping containers..."
docker compose --env-file ../.env down

# Create data directories
echo ""
echo "2. Creating data directory structure..."
mkdir -p "$DATA_DIR"/{neo4j/{data,logs,backups},haia/{logs,transcripts},open-webui}

# Migrate Neo4j data
echo ""
echo "3. Migrating Neo4j data..."
if docker volume inspect haia_neo4j-data &>/dev/null; then
    echo "   Copying Neo4j database..."
    docker run --rm \
        -v haia_neo4j-data:/source \
        -v "$(pwd)/$DATA_DIR/neo4j/data":/target \
        alpine sh -c "cp -av /source/. /target/"
    echo "   ✓ Neo4j data migrated"
else
    echo "   No existing Neo4j volume found (fresh install)"
fi

# Migrate OpenWebUI data
echo ""
echo "4. Migrating OpenWebUI data..."
if docker volume inspect haia_open-webui-data &>/dev/null; then
    echo "   Copying chat history and settings..."
    docker run --rm \
        -v haia_open-webui-data:/source \
        -v "$(pwd)/$DATA_DIR/open-webui":/target \
        alpine sh -c "cp -av /source/. /target/"
    echo "   ✓ OpenWebUI data migrated"
else
    echo "   No existing OpenWebUI volume found (fresh install)"
fi

# Set permissions (ignore errors for Docker-owned files)
echo ""
echo "5. Setting permissions..."
chmod -R 755 "$DATA_DIR" 2>/dev/null || echo "   Some files owned by Docker (this is normal)"

# Start with new configuration
echo ""
echo "6. Starting containers with bind mounts..."
docker compose --env-file ../.env up -d

echo ""
echo "Migration complete! ✓"
echo ""
echo "Your data is now in: $DATA_DIR"
echo ""
echo "To backup:"
echo "  tar -czf haia-backup-\$(date +%Y%m%d).tar.gz -C .. data/"
echo ""
echo "To migrate to new server:"
echo "  1. Copy data/ directory to new server"
echo "  2. Copy .env file"
echo "  3. Run: docker compose up -d"
echo ""
echo "Old named volumes can be cleaned up with:"
echo "  docker volume rm haia_neo4j-data haia_neo4j-logs haia_neo4j-backups haia_haia-logs haia_open-webui-data"
