# HAIA Data Management Guide

## Data Storage

All persistent data is stored in **local bind mounts** for easy backup and migration.

### Directory Structure

```
data/
├── haia/
│   ├── logs/          # HAIA application logs
│   └── transcripts/   # Conversation transcripts (boundary detection)
├── neo4j/
│   ├── data/          # Neo4j graph database (ALL MEMORIES)
│   ├── logs/          # Neo4j server logs
│   └── backups/       # Manual Neo4j backups
└── open-webui/
    ├── cache/         # Model caches
    ├── uploads/       # User-uploaded files
    ├── vector_db/     # OpenWebUI vector store
    └── webui.db       # Chat history & user accounts
```

**Total size**: ~1-5GB (depends on conversation history and cached models)

## Backup

### Quick Backup (Recommended)

```bash
# Create timestamped backup
tar -czf haia-backup-$(date +%Y%m%d-%H%M%S).tar.gz data/

# Or just the critical data (Neo4j + OpenWebUI)
tar -czf haia-critical-$(date +%Y%m%d-%H%M%S).tar.gz \
  data/neo4j/data/ \
  data/open-webui/webui.db \
  data/open-webui/vector_db/
```

### Automated Backup Script

```bash
#!/bin/bash
# Add to crontab: 0 2 * * * /path/to/backup-haia.sh

BACKUP_DIR="/path/to/backups"
DATE=$(date +%Y%m%d-%H%M%S)

# Stop containers for consistent backup
docker compose -f /path/to/deployment/docker-compose.yml down

# Create backup
tar -czf "$BACKUP_DIR/haia-$DATE.tar.gz" \
  -C /path/to/haia data/

# Restart containers
docker compose -f /path/to/deployment/docker-compose.yml up -d

# Keep only last 7 days
find "$BACKUP_DIR" -name "haia-*.tar.gz" -mtime +7 -delete
```

## Migration to New Server

### Step 1: Backup on Old Server

```bash
# Stop containers gracefully
docker compose -f deployment/docker-compose.yml down

# Create backup
tar -czf haia-migration.tar.gz data/ .env

# Copy to new server
scp haia-migration.tar.gz user@new-server:/path/to/haia/
```

### Step 2: Restore on New Server

```bash
# Extract backup
tar -xzf haia-migration.tar.gz

# Start containers
docker compose -f deployment/docker-compose.yml --env-file .env up -d

# Verify
docker compose ps
curl http://localhost:3000  # OpenWebUI
curl http://localhost:8000/health  # HAIA API
```

**All memories, conversations, and settings preserved!** ✓

## Custom Data Location

To use a different data directory (e.g., on separate drive):

### Option 1: Environment Variable

```bash
# In .env file
DATA_DIR=/mnt/storage/haia-data
```

### Option 2: Symlink

```bash
# Move data to external drive
mv data/ /mnt/storage/haia-data/

# Create symlink
ln -s /mnt/storage/haia-data data
```

### Option 3: Bind Mount Override

```bash
# In .env
DATA_DIR=/mnt/external/haia

# Restart
docker compose down && docker compose up -d
```

## Recovering from Data Loss

### Scenario 1: Neo4j Database Corruption

```bash
# Stop containers
docker compose down

# Restore from backup
rm -rf data/neo4j/data/*
tar -xzf haia-backup-YYYYMMDD.tar.gz data/neo4j/data/

# Start containers
docker compose up -d
```

### Scenario 2: OpenWebUI Reset

```bash
# Keep Neo4j (memories), reset OpenWebUI (chat interface)
docker compose down
rm -rf data/open-webui/
docker compose up -d

# Re-create user account, all memories intact
```

### Scenario 3: Complete Reset

```bash
# Nuclear option: Start fresh
docker compose down -v
rm -rf data/
docker compose up -d
```

## Data Portability

### Export Memories to JSON

```cypher
// Connect to Neo4j Browser: http://localhost:7474
MATCH (m:Memory)
RETURN m.content, m.type, m.confidence, m.valid_from
  AS memories
```

Export as JSON for archival.

### Export Conversations

```bash
# OpenWebUI chat history
docker exec haia-webui sqlite3 /app/backend/data/webui.db \
  ".dump chat" > conversations-export.sql
```

## Monitoring Disk Usage

```bash
# Check data directory size
du -sh data/*

# Monitor in real-time
watch -n 5 'du -sh data/*'

# Per-container usage
docker system df -v | grep haia
```

## Security Notes

- **data/ directory is gitignored** - never committed to repository
- Contains **personal information**: conversation history, user accounts
- **Encrypt backups** when storing externally
- **Neo4j password** protects database access
- **OpenWebUI accounts** protect chat interface

## Cleanup

### Remove Old Named Volumes (After Migration)

```bash
# List old volumes
docker volume ls | grep haia

# Remove (data already migrated to bind mounts)
docker volume rm \
  haia_neo4j-data \
  haia_neo4j-logs \
  haia_neo4j-backups \
  haia_haia-logs \
  haia_open-webui-data
```

### Clear Docker Cache

```bash
# Free up space
docker system prune -a --volumes

# Be careful: This removes ALL unused Docker data
```

---

**Questions?** See deployment/docker-compose.yml for volume configuration.
