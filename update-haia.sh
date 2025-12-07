#!/bin/bash
# Update Haia configuration and restart service
# Usage: sudo ./update-haia.sh

set -e

echo "Updating Haia configuration..."

# Define paths
DEV_DIR="/home/vlb/Python/haia"
PROD_DIR="/opt/haia"
HAIA_USER="haia"
HAIA_GROUP="haia"

# Copy .env file
if [ -f "$DEV_DIR/.env" ]; then
    echo "Copying .env file..."
    cp "$DEV_DIR/.env" "$PROD_DIR/.env"
    chown $HAIA_USER:$HAIA_GROUP "$PROD_DIR/.env"
    chmod 600 "$PROD_DIR/.env"
    echo "✓ .env updated"
else
    echo "⚠ No .env file found in $DEV_DIR"
fi

# Copy profile file
if [ -f "$DEV_DIR/vincent_profile.yaml" ]; then
    echo "Copying profile file..."
    cp "$DEV_DIR/vincent_profile.yaml" "$PROD_DIR/vincent_profile.yaml"
    chown $HAIA_USER:$HAIA_GROUP "$PROD_DIR/vincent_profile.yaml"
    chmod 644 "$PROD_DIR/vincent_profile.yaml"
    echo "✓ Profile updated"
else
    echo "⚠ No vincent_profile.yaml file found in $DEV_DIR"
fi

# Restart service
echo "Restarting Haia service..."
systemctl restart haia

# Check status
echo ""
echo "Service status:"
systemctl status haia --no-pager -l | head -n 10

echo ""
echo "✓ Haia configuration updated and service restarted"
