#!/bin/bash
# Haia Cleanup Script - removes existing installation completely
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

echo -e "${YELLOW}=== Cleaning up Haia installation ===${NC}\n"

# Step 1: Stop and disable service
echo -e "${YELLOW}[1/5] Stopping Haia service...${NC}"
if systemctl is-active --quiet haia; then
    systemctl stop haia
    echo "Service stopped"
else
    echo "Service not running"
fi

if systemctl is-enabled --quiet haia 2>/dev/null; then
    systemctl disable haia
    echo "Service disabled"
fi

# Step 2: Remove systemd service file
echo -e "${YELLOW}[2/5] Removing systemd service file...${NC}"
if [ -f /etc/systemd/system/haia.service ]; then
    rm -f /etc/systemd/system/haia.service
    systemctl daemon-reload
    echo "Service file removed"
else
    echo "No service file found"
fi

# Step 3: Check for running processes
echo -e "${YELLOW}[3/5] Checking for running processes...${NC}"
if id "haia" &>/dev/null; then
    PROCS=$(ps -u haia -o pid= 2>/dev/null | wc -l)
    if [ "$PROCS" -gt 0 ]; then
        echo -e "${RED}Warning: Found $PROCS processes running as haia user${NC}"
        ps -u haia -o pid,cmd
        echo -e "${YELLOW}Killing processes...${NC}"
        pkill -u haia || true
        sleep 2
    else
        echo "No processes running as haia user"
    fi
else
    echo "User haia does not exist"
fi

# Step 4: Remove user and home directory
echo -e "${YELLOW}[4/5] Removing haia user...${NC}"
if id "haia" &>/dev/null; then
    userdel -r haia 2>/dev/null || {
        echo -e "${YELLOW}Warning: Could not remove user with -r flag, trying force removal...${NC}"
        userdel -f haia 2>/dev/null || true
    }
    echo "User removed"
else
    echo "User already removed"
fi

# Step 5: Clean up remaining files
echo -e "${YELLOW}[5/5] Removing /opt/haia directory...${NC}"
if [ -d /opt/haia ]; then
    rm -rf /opt/haia
    echo "Directory removed"
else
    echo "Directory does not exist"
fi

echo -e "\n${GREEN}=== Cleanup Complete! ===${NC}\n"
echo -e "You can now run the installation script:"
echo -e "${YELLOW}sudo bash deployment/install.sh${NC}"
