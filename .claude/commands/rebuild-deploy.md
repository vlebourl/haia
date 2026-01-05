---
description: Rebuild HAIA Docker container from scratch (no cache) and redeploy the latest version
---

## User Input

```text
$ARGUMENTS
```

Optional: User can specify additional flags (e.g., "verbose" for more detailed logs)

## Outline

Execute these steps to rebuild and redeploy the HAIA container from scratch:

### Step 1: Verify Location and Prerequisites

1. Check current working directory:
   ```bash
   pwd
   ```

2. If not in `/home/vlb/Python/haia`, navigate there:
   ```bash
   cd /home/vlb/Python/haia
   ```

3. Verify Docker is running:
   ```bash
   docker ps > /dev/null 2>&1 && echo "✓ Docker is running" || echo "✗ Docker is not running - start it first"
   ```

### Step 2: Stop Running Containers

Stop all HAIA services gracefully:

```bash
docker compose -f deployment/docker-compose.yml down
```

**Expected**: Containers stopping, networks being removed.

### Step 3: Clean Old Images and Build Cache

Remove old HAIA image and clean build cache:

```bash
# Remove old HAIA image (ignore error if doesn't exist)
docker rmi deployment-haia 2>/dev/null || echo "No old image to remove"

# Prune build cache for fresh build
docker builder prune -f
```

**Expected**: Build cache deletion confirmation.

### Step 4: Rebuild Container from Scratch

Build with no cache to ensure all changes are picked up:

```bash
docker compose -f deployment/docker-compose.yml build --no-cache haia
```

**Expected**:
- Building steps from Dockerfile
- Python dependencies being installed
- "Successfully tagged deployment-haia:latest"

**Note**: This takes 2-5 minutes depending on network speed.

### Step 5: Start Services

Start all services with the rebuilt container:

```bash
docker compose -f deployment/docker-compose.yml up -d
```

**Expected**:
- Containers starting (haia-api, haia-neo4j)
- "Container haia-api Started"

### Step 6: Verify Deployment

Check that services are running correctly:

```bash
# Container status
docker compose -f deployment/docker-compose.yml ps

# Wait a few seconds for startup
sleep 5

# Check HAIA logs
docker logs haia-api --tail 50
```

**Look for in logs**:
- "Starting HAIA Chat API server..."
- "Neo4j connection established"
- "Vector index 'memory_embeddings' ready"
- "Server startup complete - ready to accept requests"

### Step 7: Health Check

Perform API health check:

```bash
curl -s http://localhost:8000/health | jq '.' || curl -s http://localhost:8000/health
```

**Expected**: JSON response with status information.

### Step 8: Summary Report

After all steps complete, provide a summary:

```text
✅ REBUILD AND DEPLOY COMPLETE

Summary:
- Old containers stopped: ✓
- Build cache cleaned: ✓
- Container rebuilt from scratch: ✓
- Services started: ✓
- Health check: [PASS/FAIL]

Services Running:
[List containers from docker ps output]

Next Steps:
1. Test with a chat request to verify memory retrieval
2. Monitor logs for any errors: docker logs -f haia-api
3. Check Neo4j UI if needed: http://localhost:7474

Downtime: ~[X] minutes
```

## Error Handling

### If build fails:
- Display the error from docker build
- Check disk space: `df -h`
- Check Docker daemon: `sudo systemctl status docker`
- Suggest reviewing Dockerfile and requirements.txt

### If containers won't start:
- Display logs: `docker logs haia-api`
- Check for port conflicts: `netstat -tuln | grep -E '8000|7687|7474'`
- Verify .env file has required keys:
  - ANTHROPIC_API_KEY
  - NEO4J_PASSWORD
  - GOOGLE_API_KEY (if using Google embeddings)

### If health check fails:
- Wait 10 more seconds and retry
- Check logs for startup errors
- Verify Neo4j is ready: `docker logs haia-neo4j`

## Safety Notes

**Data Preservation**:
- ✅ Neo4j data preserved in Docker volumes
- ✅ .env configuration not affected
- ✅ Conversation transcripts preserved (if stored in DATA_DIR)

**Downtime**:
- Expect 2-5 minutes of downtime
- Any active chat sessions will be disconnected

**What This Does NOT Do**:
- Does not modify .env configuration
- Does not delete Neo4j data or volumes
- Does not change git branch or commit code
- Does not affect database schema (migrations run automatically)

## Related Commands

If you don't need a full rebuild:
- Quick restart: `docker compose -f deployment/docker-compose.yml restart`
- Stop only: `docker compose -f deployment/docker-compose.yml down`
- Start existing: `docker compose -f deployment/docker-compose.yml up -d`
- View logs: `docker logs -f haia-api`
