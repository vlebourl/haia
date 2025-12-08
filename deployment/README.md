# HAIA Deployment Files

This directory contains files for deploying HAIA in production with two deployment modes:

1. **Docker Compose** (Recommended): Containerized deployment with Neo4j memory database
2. **Systemd Service**: Native deployment on Ubuntu/Debian systems

## Files

### Docker Compose Deployment (Recommended)

#### `docker-compose.yml`
Multi-service orchestration for HAIA + Neo4j with health checks, volume persistence, and custom networking.

#### `Dockerfile`
Production container image for HAIA with multi-stage build for optimized size.

#### `docker-install.sh`
One-command deployment script that:
1. Validates Docker and environment configuration
2. Builds HAIA container image
3. Starts both services (HAIA + Neo4j)
4. Applies Neo4j schema
5. Runs health checks

Usage:
```bash
chmod +x deployment/docker-install.sh
./deployment/docker-install.sh
```

#### `docker-compose.dev.yml` (User Story 3)
Development overrides for hybrid deployment (native HAIA + containerized Neo4j).

### Systemd Service Deployment

#### `haia.service`
Systemd service unit file for running Haia as a system service.
- Runs as dedicated `haia` user
- Auto-restart on failure
- Security hardening enabled
- Logs to systemd journal

#### `install.sh`
Automated installation script for Ubuntu.
```bash
sudo bash deployment/install.sh
```

This script will:
1. Install system dependencies (Python 3.11, git, etc.)
2. Create dedicated `haia` user
3. Clone repository to `/opt/haia`
4. Set up Python virtual environment
5. Install Haia and dependencies
6. Configure environment file
7. Install and enable systemd service

#### `DEPLOYMENT.md`
Comprehensive deployment guide covering:
- Manual installation steps
- Configuration
- Service management
- Reverse proxy setup
- Troubleshooting
- Security considerations
- Backup and recovery

## Docker Volume Backup Procedures (User Story 2)

Docker volumes persist data across container restarts and recreations. To protect your Neo4j memory data:

### Manual Volume Backup

```bash
# Create backup directory
mkdir -p ~/haia-backups

# Backup Neo4j data volume
docker run --rm \
  -v haia_neo4j-data:/source \
  -v ~/haia-backups:/backup \
  alpine tar czf /backup/neo4j-data-$(date +%Y%m%d-%H%M%S).tar.gz -C /source .
```

### Volume Restore

```bash
# Stop services
docker compose -f deployment/docker-compose.yml down

# Restore Neo4j data volume
docker run --rm \
  -v haia_neo4j-data:/target \
  -v ~/haia-backups:/backup \
  alpine sh -c "cd /target && tar xzf /backup/neo4j-data-YYYYMMDD-HHMMSS.tar.gz"

# Restart services
docker compose -f deployment/docker-compose.yml up -d
```

### Automated Backup Script

```bash
# Create backup script
cat > ~/haia-volume-backup.sh <<'EOF'
#!/bin/bash
BACKUP_DIR=~/haia-backups
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d-%H%M%S)

docker run --rm \
  -v haia_neo4j-data:/source \
  -v "$BACKUP_DIR":/backup \
  alpine tar czf /backup/neo4j-data-${TIMESTAMP}.tar.gz -C /source .

# Keep last 7 backups
find "$BACKUP_DIR" -name "neo4j-data-*.tar.gz" -mtime +7 -delete
EOF

chmod +x ~/haia-volume-backup.sh

# Add to crontab (daily at 3 AM)
(crontab -l 2>/dev/null; echo "0 3 * * * ~/haia-volume-backup.sh") | crontab -
```

For Neo4j-native backups, see `database/backups/README.md` (User Story 6).

---

## Quick Start

### Option 1: Docker Compose (Recommended)

```bash
# 1. Configure environment
cp .env.example .env
nano .env  # Edit NEO4J_PASSWORD and other settings

# 2. Deploy stack
chmod +x deployment/docker-install.sh
./deployment/docker-install.sh

# 3. Verify deployment
curl http://localhost:8000/health
open http://localhost:7474  # Neo4j Browser
```

### Option 2: Systemd Service (Automated Installation)

```bash
# Download and run installation script
curl -O https://raw.githubusercontent.com/vlebourl/haia/main/deployment/install.sh
sudo bash install.sh

# Configure
sudo nano /opt/haia/.env
sudo -u haia nano /opt/haia/vincent_profile.yaml

# Start service
sudo systemctl start haia
sudo systemctl status haia
```

### Option 2: Manual Installation

Follow the detailed steps in [DEPLOYMENT.md](DEPLOYMENT.md).

## Post-Installation

After installation:

1. **Configure API Key**: Edit `/opt/haia/.env` with your Anthropic API key
2. **Create Profile**: Copy and customize your homelab profile
3. **Start Service**: `sudo systemctl start haia`
4. **Check Logs**: `sudo journalctl -u haia -f`
5. **Test API**:
   ```bash
   curl -X POST http://localhost:8000/v1/chat/completions \
     -H "Content-Type: application/json" \
     -d '{"model": "haia", "messages": [{"role": "user", "content": "Hello!"}]}'
   ```

## Service Management Commands

```bash
# Start service
sudo systemctl start haia

# Stop service
sudo systemctl stop haia

# Restart service
sudo systemctl restart haia

# View status
sudo systemctl status haia

# Enable auto-start on boot
sudo systemctl enable haia

# Disable auto-start
sudo systemctl disable haia

# View logs
sudo journalctl -u haia -f
```

## Directory Structure After Installation

```
/opt/haia/
├── .venv/              # Python virtual environment
├── .env                # Environment configuration (DO NOT COMMIT)
├── vincent_profile.yaml # Homelab profile (DO NOT COMMIT)
├── src/                # Source code
├── deployment/         # Deployment files (this directory)
├── haia.db            # SQLite database
└── pyproject.toml     # Python project configuration
```

## Security Notes

- Service runs as non-privileged `haia` user
- `.env` file has restricted permissions (600)
- Systemd hardening options enabled
- Logs to journal (managed by systemd)

## Troubleshooting

See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed troubleshooting guide.

Common issues:
- **Port 8000 in use**: Change PORT in `.env`
- **Permission denied**: Check file ownership with `ls -la /opt/haia/`
- **Import errors**: Reinstall with `sudo -u haia /opt/haia/.venv/bin/uv pip install -e /opt/haia`
- **Service won't start**: Check logs with `sudo journalctl -u haia -n 50`

## Support

- GitHub: https://github.com/vlebourl/haia
- Issues: https://github.com/vlebourl/haia/issues
- Documentation: [DEPLOYMENT.md](DEPLOYMENT.md)
