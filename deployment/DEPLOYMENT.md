# Haia Production Deployment Guide

This guide walks you through deploying Haia as a production service on Ubuntu.

## Prerequisites

- Ubuntu 20.04+ (or Debian-based system)
- Python 3.11+
- sudo/root access
- Git

## Installation Steps

### 1. Install System Dependencies

```bash
# Update system packages
sudo apt update && sudo apt upgrade -y

# Install Python 3.11 and development tools
sudo apt install -y python3.11 python3.11-venv python3-pip git

# Install uv (modern Python package installer)
curl -LsSf https://astral.sh/uv/install.sh | sh
source $HOME/.cargo/env
```

### 2. Create Dedicated User

For security, run Haia as a dedicated non-privileged user:

```bash
# Create haia user and group
sudo useradd --system --create-home --home-dir /opt/haia --shell /bin/bash haia

# Switch to haia user for installation
sudo su - haia
```

### 3. Clone and Install Haia

```bash
# Clone the repository (as haia user)
cd /opt/haia
git clone https://github.com/vlebourl/haia.git .

# Create virtual environment with Python 3.11
python3.11 -m venv .venv

# Activate virtual environment
source .venv/bin/activate

# Install uv in the virtual environment
pip install uv

# Install haia and dependencies
uv pip install -e .
```

### 4. Configure Environment

```bash
# Copy example configuration
cp .env.example .env

# Edit configuration with your settings
nano .env
```

**Required configuration in `.env`:**

```bash
# Anthropic API Configuration
ANTHROPIC_API_KEY=sk-ant-api03-your-actual-key-here

# Model Configuration
HAIA_MODEL=anthropic:claude-haiku-4-5-20251001

# System Prompt (copy from your personalized .env)
HAIA_SYSTEM_PROMPT="Your comprehensive Haia personality prompt..."

# Homelab Profile
HAIA_PROFILE_PATH=vincent_profile.yaml  # Or your profile name

# Context Window
CONTEXT_WINDOW_SIZE=100

# Server Configuration
HOST=0.0.0.0
PORT=8000

# Database
DATABASE_URL=sqlite+aiosqlite:///opt/haia/haia.db
```

### 5. Create Your Homelab Profile

```bash
# Copy example profile
cp haia_profile.example.yaml vincent_profile.yaml  # Or your name

# Edit with your homelab details
nano vincent_profile.yaml
```

### 6. Set Permissions

```bash
# Exit haia user shell
exit

# Set ownership (as root/sudo user)
sudo chown -R haia:haia /opt/haia
sudo chmod 600 /opt/haia/.env
sudo chmod 600 /opt/haia/*_profile.yaml
```

### 7. Install Systemd Service

```bash
# Copy service file to systemd directory
sudo cp /opt/haia/deployment/haia.service /etc/systemd/system/

# Reload systemd to recognize new service
sudo systemctl daemon-reload

# Enable service to start on boot
sudo systemctl enable haia

# Start the service
sudo systemctl start haia
```

### 8. Verify Installation

```bash
# Check service status
sudo systemctl status haia

# View logs
sudo journalctl -u haia -f

# Test API endpoint
curl http://localhost:8000/health  # If you have a health endpoint
# Or test the chat endpoint
curl -X POST http://localhost:8000/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "haia",
    "messages": [{"role": "user", "content": "Hello Haia!"}],
    "stream": false
  }'
```

## Service Management

### Start/Stop/Restart

```bash
# Start service
sudo systemctl start haia

# Stop service
sudo systemctl stop haia

# Restart service
sudo systemctl restart haia

# Check status
sudo systemctl status haia
```

### View Logs

```bash
# Follow logs in real-time
sudo journalctl -u haia -f

# View last 100 lines
sudo journalctl -u haia -n 100

# View logs from today
sudo journalctl -u haia --since today

# View logs with full output
sudo journalctl -u haia --no-pager
```

### Update Haia

```bash
# Switch to haia user
sudo su - haia

# Pull latest changes
cd /opt/haia
git pull

# Update dependencies
source .venv/bin/activate
uv pip install -e . --upgrade

# Exit haia user
exit

# Restart service to apply updates
sudo systemctl restart haia
```

## Reverse Proxy Setup (Optional)

### Nginx Configuration

If you want to access Haia through a reverse proxy:

```nginx
# /etc/nginx/sites-available/haia
server {
    listen 80;
    server_name haia.yourdomain.com;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (for SSE streaming)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_read_timeout 86400;
    }
}
```

Enable the site:
```bash
sudo ln -s /etc/nginx/sites-available/haia /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Using Nginx Proxy Manager

Since Vincent already has Nginx Proxy Manager (LXC 105), you can configure Haia through the NPM web UI:

1. **Proxy Host Settings**:
   - Domain: `haia.yourlab.local` (or your chosen domain)
   - Scheme: `http`
   - Forward Hostname/IP: IP of the machine running Haia
   - Forward Port: `8000`

2. **Advanced Settings**:
   - Enable WebSocket Support
   - Add custom nginx configuration if needed:
     ```nginx
     proxy_read_timeout 86400;
     proxy_buffering off;
     ```

## Firewall Configuration

If using UFW firewall:

```bash
# Allow Haia port (if accessing directly)
sudo ufw allow 8000/tcp

# Or allow from specific network only
sudo ufw allow from 192.168.1.0/24 to any port 8000

# Check firewall status
sudo ufw status
```

## Troubleshooting

### Service Won't Start

```bash
# Check service status
sudo systemctl status haia

# Check logs for errors
sudo journalctl -u haia -n 50

# Check if port is already in use
sudo netstat -tlnp | grep 8000
```

### Permission Errors

```bash
# Verify ownership
ls -la /opt/haia/.env
ls -la /opt/haia/*_profile.yaml

# Fix permissions
sudo chown haia:haia /opt/haia/.env
sudo chmod 600 /opt/haia/.env
```

### Import Errors

```bash
# Reinstall dependencies
sudo su - haia
cd /opt/haia
source .venv/bin/activate
uv pip install -e . --force-reinstall
```

### Database Issues

```bash
# Check database file permissions
ls -la /opt/haia/haia.db

# Reset database (WARNING: deletes all data)
sudo su - haia
cd /opt/haia
rm haia.db
# Restart service to recreate
exit
sudo systemctl restart haia
```

## Security Considerations

1. **API Key Security**:
   - Never commit `.env` to git
   - Restrict `.env` permissions to 600
   - Rotate API keys regularly

2. **Network Security**:
   - Run behind reverse proxy in production
   - Use firewall to restrict access
   - Consider VPN for external access

3. **User Isolation**:
   - Service runs as dedicated `haia` user
   - Limited filesystem access via systemd
   - No shell access for haia user

4. **Updates**:
   - Regularly update dependencies
   - Monitor security advisories
   - Test updates in non-production first

## Performance Tuning

### For High Traffic

If you need better performance, consider:

1. **Multiple Workers** (edit service file):
   ```ini
   ExecStart=/opt/haia/.venv/bin/uvicorn haia.api.app:app --host 0.0.0.0 --port 8000 --workers 4
   ```

2. **Gunicorn with Uvicorn Workers**:
   ```bash
   # Install gunicorn
   uv pip install gunicorn

   # Update service ExecStart
   ExecStart=/opt/haia/.venv/bin/gunicorn haia.api.app:app -w 4 -k uvicorn.workers.UvicornWorker -b 0.0.0.0:8000
   ```

3. **Database Optimization**:
   - Consider PostgreSQL for multi-user setups
   - Use connection pooling

## Monitoring

### Systemd Journal Integration

Haia logs to systemd journal automatically. Monitor with:

```bash
# Real-time monitoring
sudo journalctl -u haia -f

# Filter by priority
sudo journalctl -u haia -p err  # Errors only

# Export logs
sudo journalctl -u haia --since "1 hour ago" > haia-logs.txt
```

### Integration with Prometheus/Grafana

For advanced monitoring, you can:
1. Export metrics from Haia (future enhancement)
2. Monitor service status via systemd
3. Parse logs for error rates

## Backup and Recovery

### What to Backup

```bash
# Configuration files
/opt/haia/.env
/opt/haia/*_profile.yaml

# Database
/opt/haia/haia.db

# Custom modifications (if any)
/opt/haia/src/
```

### Backup Script Example

```bash
#!/bin/bash
# /opt/haia/backup.sh

BACKUP_DIR="/backup/haia/$(date +%Y%m%d_%H%M%S)"
mkdir -p "$BACKUP_DIR"

cp /opt/haia/.env "$BACKUP_DIR/"
cp /opt/haia/*_profile.yaml "$BACKUP_DIR/"
cp /opt/haia/haia.db "$BACKUP_DIR/"

echo "Backup created: $BACKUP_DIR"
```

## Support

For issues or questions:
- GitHub Issues: https://github.com/vlebourl/haia/issues
- Check logs: `sudo journalctl -u haia -n 100`
- Service status: `sudo systemctl status haia`
