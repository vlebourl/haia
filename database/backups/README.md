# HAIA Neo4j Backup and Recovery

**Purpose**: Automated daily backups with 7-day rotation and documented recovery procedures.

## Overview

The backup system provides:
- **Automated daily backups** using neo4j-admin dump
- **7-day rotation policy** (automatic deletion of backups older than 7 days)
- **Full database restoration** from any backup file
- **Safety backups** created before restore operations
- **Volume-based persistence** (backups stored in Docker volume `haia_neo4j-backups`)

## Quick Start

### Create a Backup

```bash
# Manual backup (anytime)
./database/backups/backup.sh

# Specify database name (optional, defaults to 'neo4j')
./database/backups/backup.sh neo4j
```

### Restore from Backup

```bash
# List available backups
docker exec haia-neo4j ls -lh /backups/haia_backup_*.dump

# Restore from specific backup
./database/backups/restore.sh haia_backup_neo4j_20251208_120000.dump
```

**⚠️ WARNING**: Restore will REPLACE all current data!

## Automated Backup Schedule

### Option 1: Host Cron (Recommended for Production)

Add to your host's crontab:

```bash
# Edit crontab
crontab -e

# Add daily backup at 2 AM
0 2 * * * /path/to/haia/database/backups/backup.sh >> /var/log/haia-backup.log 2>&1
```

### Option 2: Docker Container Cron

Create a cron job inside the Neo4j container:

```bash
# Enter container
docker exec -it haia-neo4j bash

# Install cron (if not present)
apt-get update && apt-get install -y cron

# Add cron job
echo "0 2 * * * neo4j-admin database dump --to-path=/backups neo4j && find /backups -name '*.dump' -mtime +7 -delete" | crontab -

# Start cron daemon
service cron start
```

### Option 3: Systemd Timer (Linux)

Create `/etc/systemd/system/haia-backup.timer`:

```ini
[Unit]
Description=HAIA Neo4j Daily Backup
Requires=haia-backup.service

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true

[Install]
WantedBy=timers.target
```

Create `/etc/systemd/system/haia-backup.service`:

```ini
[Unit]
Description=HAIA Neo4j Backup Service
After=docker.service
Requires=docker.service

[Service]
Type=oneshot
ExecStart=/path/to/haia/database/backups/backup.sh
User=youruser
StandardOutput=journal
StandardError=journal
```

Enable and start:

```bash
sudo systemctl daemon-reload
sudo systemctl enable haia-backup.timer
sudo systemctl start haia-backup.timer
sudo systemctl list-timers --all  # Verify
```

## Backup Files

### File Naming Convention

```
haia_backup_<database>_<timestamp>.dump
```

Example: `haia_backup_neo4j_20251208_143022.dump`
- Database: `neo4j`
- Date: 2025-12-08
- Time: 14:30:22

### Storage Location

**Container path**: `/backups/`
**Docker volume**: `haia_neo4j-backups`
**Host access**: Via Docker volume inspect

```bash
# Find volume location on host
docker volume inspect haia_neo4j-backups

# Copy backup to host (if needed)
docker cp haia-neo4j:/backups/haia_backup_neo4j_20251208_120000.dump ./local_backup.dump
```

### Rotation Policy

- **Retention period**: 7 days
- **Automatic cleanup**: Yes (backups older than 7 days are deleted)
- **Cleanup timing**: After each successful backup
- **Manual cleanup**: `find /backups -name 'haia_backup_*.dump' -mtime +7 -delete` (inside container)

## Recovery Procedures

### Full Database Restore

**When to use**: Data corruption, accidental deletion, rollback to previous state

**Steps**:

1. **Identify backup to restore**:
   ```bash
   docker exec haia-neo4j ls -lh /backups/haia_backup_*.dump
   ```

2. **Run restore script**:
   ```bash
   ./database/backups/restore.sh haia_backup_neo4j_20251208_120000.dump
   ```

3. **Confirm restoration**:
   - Script will prompt for confirmation
   - Creates safety backup before proceeding
   - Automatically stops/starts database

4. **Verify data**:
   ```bash
   docker exec haia-neo4j cypher-shell -u neo4j -p <password> \
     "MATCH (n) RETURN labels(n) AS type, count(n) AS count ORDER BY type"
   ```

### Partial Data Recovery

**When to use**: Need specific nodes/relationships from backup

**Steps**:

1. **Restore to temporary database**:
   ```bash
   # Inside container
   docker exec -it haia-neo4j bash
   neo4j-admin database load --from-path=/backups temp_restore --overwrite-destination=true
   ```

2. **Query specific data**:
   ```bash
   cypher-shell -u neo4j -p <password> -d temp_restore
   ```

3. **Export needed data** and import to production database

### Disaster Recovery

**Scenario**: Complete system failure, need to rebuild from scratch

**Steps**:

1. **Deploy fresh HAIA stack**:
   ```bash
   git clone <repository>
   cd haia
   ./deployment/docker-install.sh
   ```

2. **Stop Neo4j**:
   ```bash
   docker compose -f deployment/docker-compose.yml stop neo4j
   ```

3. **Copy backup file to volume**:
   ```bash
   docker cp ./backup_file.dump haia-neo4j:/backups/
   ```

4. **Restore database**:
   ```bash
   ./database/backups/restore.sh backup_file.dump
   ```

5. **Verify HAIA connectivity**:
   ```bash
   curl http://localhost:8000/health
   ```

## Backup Verification

### Automated Verification

The backup script automatically:
- Checks file size (non-zero)
- Verifies file exists and is readable

### Manual Verification

#### Test Restore (Non-Destructive)

```bash
# 1. Create test backup
./database/backups/backup.sh

# 2. Stop Neo4j
docker compose -f deployment/docker-compose.yml stop neo4j

# 3. Create test container
docker run --rm -it \
  -v haia_neo4j-backups:/backups \
  neo4j:5.15 bash

# 4. Inside test container
neo4j-admin database load --from-path=/backups test_verify
# Check for errors

# 5. Exit and remove test container
exit

# 6. Restart Neo4j
docker compose -f deployment/docker-compose.yml start neo4j
```

#### Check Backup Integrity

```bash
# Inside Neo4j container
docker exec -it haia-neo4j bash

# Verify dump file format
file /backups/haia_backup_neo4j_*.dump
# Expected: "data" or similar

# Check file size
du -h /backups/haia_backup_neo4j_*.dump
# Should be reasonable (>1MB for real data)
```

## Monitoring and Alerts

### Check Last Backup

```bash
# List backups sorted by date
docker exec haia-neo4j ls -lt /backups/haia_backup_*.dump | head -5

# Get last backup age
docker exec haia-neo4j sh -c '
  LAST_BACKUP=$(ls -t /backups/haia_backup_*.dump | head -1)
  if [ -n "$LAST_BACKUP" ]; then
    AGE_HOURS=$(( ($(date +%s) - $(stat -c %Y "$LAST_BACKUP")) / 3600 ))
    echo "Last backup: $LAST_BACKUP"
    echo "Age: ${AGE_HOURS} hours"
  else
    echo "No backups found!"
  fi
'
```

### Alert on Backup Failures

Add to your monitoring system:

```bash
#!/bin/bash
# Check if backup is less than 25 hours old
LAST_BACKUP_AGE=$(docker exec haia-neo4j sh -c '
  LAST_BACKUP=$(ls -t /backups/haia_backup_*.dump 2>/dev/null | head -1)
  if [ -n "$LAST_BACKUP" ]; then
    echo $(( ($(date +%s) - $(stat -c %Y "$LAST_BACKUP")) / 3600 ))
  else
    echo 999
  fi
')

if [ "$LAST_BACKUP_AGE" -gt 24 ]; then
  echo "ALERT: HAIA backup is ${LAST_BACKUP_AGE} hours old!"
  # Send notification (email, Slack, etc.)
fi
```

## Backup Best Practices

### Security

- **Restrict script permissions**: `chmod 700 backup.sh restore.sh`
- **Protect backups**: Store Docker volume on encrypted filesystem
- **Off-site backups**: Copy backups to remote storage regularly
- **Access control**: Limit who can run restore.sh

### Performance

- **Schedule during low-usage hours**: 2-4 AM recommended
- **Monitor backup duration**: Should complete in seconds for typical usage
- **Storage capacity**: Ensure sufficient disk space (3-5x database size)

### Testing

- **Monthly restore tests**: Verify backups are restorable
- **Document restore procedures**: Keep this README updated
- **Practice disaster recovery**: Run through full DR scenario quarterly

## Troubleshooting

### Backup Script Fails

```bash
# Check container is running
docker ps | grep haia-neo4j

# Check Neo4j logs
docker logs haia-neo4j --tail 50

# Check backup volume
docker volume inspect haia_neo4j-backups

# Check disk space
docker exec haia-neo4j df -h /backups
```

### Restore Script Fails

```bash
# Check backup file exists
docker exec haia-neo4j ls -lh /backups/haia_backup_*.dump

# Check Neo4j status
docker exec haia-neo4j cypher-shell -u neo4j -p <password> "SHOW DATABASES"

# Check Neo4j logs during restore
docker logs -f haia-neo4j
```

### Permission Denied Errors

```bash
# Fix script permissions
chmod +x database/backups/*.sh

# Check Docker volume permissions
docker exec haia-neo4j ls -la /backups
```

## See Also

- Docker Compose configuration: `deployment/docker-compose.yml`
- Neo4j schema: `database/schema/README.md`
- Deployment guide: `deployment/README.md`
- Integration tests: `tests/integration/test_backup_restore.py`
