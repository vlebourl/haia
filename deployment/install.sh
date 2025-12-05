#!/bin/bash
# Haia Production Installation Script for Ubuntu
# Run as root or with sudo

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check if running as root
if [[ $EUID -ne 0 ]]; then
   echo -e "${RED}This script must be run as root or with sudo${NC}"
   exit 1
fi

echo -e "${GREEN}=== Haia Production Installation ===${NC}\n"

# Configuration
HAIA_USER="haia"
HAIA_HOME="/opt/haia"

# Detect Python version (need 3.11 or higher)
if command -v python3.13 &> /dev/null; then
    PYTHON_CMD="python3.13"
    PYTHON_VERSION="3.13"
elif command -v python3.12 &> /dev/null; then
    PYTHON_CMD="python3.12"
    PYTHON_VERSION="3.12"
elif command -v python3.11 &> /dev/null; then
    PYTHON_CMD="python3.11"
    PYTHON_VERSION="3.11"
elif command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
    PYTHON_VERSION=$(python3 --version | cut -d' ' -f2 | cut -d'.' -f1,2)
else
    echo -e "${RED}Python 3.11+ not found. Please install Python 3.11 or higher.${NC}"
    exit 1
fi

# Verify Python version is 3.11+
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d'.' -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d'.' -f2)
if [ "$PYTHON_MAJOR" -lt 3 ] || ([ "$PYTHON_MAJOR" -eq 3 ] && [ "$PYTHON_MINOR" -lt 11 ]); then
    echo -e "${RED}Python $PYTHON_VERSION found, but Haia requires Python 3.11+${NC}"
    exit 1
fi

echo -e "${GREEN}Found Python $PYTHON_VERSION at $(which $PYTHON_CMD)${NC}"

# Step 1: Install system dependencies
echo -e "${YELLOW}[1/7] Installing system dependencies...${NC}"
apt update
apt install -y python3-venv python3-pip git curl

# Step 2: Create haia user
echo -e "${YELLOW}[2/7] Creating haia user...${NC}"
if id "$HAIA_USER" &>/dev/null; then
    echo "User $HAIA_USER already exists, skipping..."
else
    useradd --system --create-home --home-dir "$HAIA_HOME" --shell /bin/bash "$HAIA_USER"
    echo "User $HAIA_USER created"
fi

# Step 3: Clone repository
echo -e "${YELLOW}[3/7] Cloning Haia repository...${NC}"
if [ -d "$HAIA_HOME/.git" ]; then
    echo "Repository already exists, pulling latest..."
    cd "$HAIA_HOME"
    sudo -u "$HAIA_USER" git pull
else
    echo "Enter the repository URL (default: https://github.com/vlebourl/haia.git):"
    read -r REPO_URL
    REPO_URL=${REPO_URL:-https://github.com/vlebourl/haia.git}

    sudo -u "$HAIA_USER" git clone "$REPO_URL" "$HAIA_HOME"
fi

# Step 4: Create virtual environment and install
echo -e "${YELLOW}[4/7] Setting up Python environment...${NC}"
cd "$HAIA_HOME"
sudo -u "$HAIA_USER" $PYTHON_CMD -m venv .venv
sudo -u "$HAIA_USER" .venv/bin/pip install --upgrade pip
sudo -u "$HAIA_USER" .venv/bin/pip install uv
sudo -u "$HAIA_USER" .venv/bin/uv pip install -e .

# Step 5: Configure environment
echo -e "${YELLOW}[5/7] Configuring environment...${NC}"
if [ ! -f "$HAIA_HOME/.env" ]; then
    sudo -u "$HAIA_USER" cp "$HAIA_HOME/.env.example" "$HAIA_HOME/.env"
    echo -e "${GREEN}Created .env file from template${NC}"
    echo -e "${YELLOW}IMPORTANT: Edit $HAIA_HOME/.env with your API keys and configuration${NC}"
else
    echo ".env already exists, skipping..."
fi

# Step 6: Set permissions
echo -e "${YELLOW}[6/7] Setting permissions...${NC}"
chown -R "$HAIA_USER:$HAIA_USER" "$HAIA_HOME"
chmod 600 "$HAIA_HOME/.env"

# Step 7: Install systemd service
echo -e "${YELLOW}[7/7] Installing systemd service...${NC}"
cp "$HAIA_HOME/deployment/haia.service" /etc/systemd/system/
systemctl daemon-reload
systemctl enable haia

echo -e "\n${GREEN}=== Installation Complete! ===${NC}\n"
echo -e "Next steps:"
echo -e "1. Edit configuration: ${YELLOW}sudo nano $HAIA_HOME/.env${NC}"
echo -e "   - Set your ANTHROPIC_API_KEY"
echo -e "   - Configure HAIA_SYSTEM_PROMPT"
echo -e "   - Set HAIA_PROFILE_PATH"
echo -e ""
echo -e "2. Create homelab profile: ${YELLOW}sudo -u $HAIA_USER cp $HAIA_HOME/haia_profile.example.yaml $HAIA_HOME/your_profile.yaml${NC}"
echo -e "   - Edit with your homelab details"
echo -e ""
echo -e "3. Start service: ${YELLOW}sudo systemctl start haia${NC}"
echo -e ""
echo -e "4. Check status: ${YELLOW}sudo systemctl status haia${NC}"
echo -e ""
echo -e "5. View logs: ${YELLOW}sudo journalctl -u haia -f${NC}"
echo -e ""
echo -e "For detailed documentation, see: $HAIA_HOME/deployment/DEPLOYMENT.md"
