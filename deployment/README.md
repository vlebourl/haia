# Haia Deployment Files

This directory contains files for deploying Haia as a production service on Ubuntu/Debian systems.

## Files

### `haia.service`
Systemd service unit file for running Haia as a system service.
- Runs as dedicated `haia` user
- Auto-restart on failure
- Security hardening enabled
- Logs to systemd journal

### `install.sh`
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

### `DEPLOYMENT.md`
Comprehensive deployment guide covering:
- Manual installation steps
- Configuration
- Service management
- Reverse proxy setup
- Troubleshooting
- Security considerations
- Backup and recovery

## Quick Start

### Option 1: Automated Installation

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
