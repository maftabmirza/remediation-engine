#!/bin/bash
# Fix Alertmanager webhook URL

# Find the config file mount location
echo "Finding Alertmanager config mount..."
docker inspect alertmanager --format='{{range .Mounts}}{{if eq .Destination "/etc/alertmanager"}}{{.Source}}{{end}}{{end}}'

# Store in variable
CONFIG_DIR=$(docker inspect alertmanager --format='{{range .Mounts}}{{if eq .Destination "/etc/alertmanager"}}{{.Source}}{{end}}{{end}}')

if [ -z "$CONFIG_DIR" ]; then
    echo "Could not find Alertmanager config directory"
    exit 1
fi

echo "Config directory: $CONFIG_DIR"
echo "Config file: $CONFIG_DIR/alertmanager.yml"

# Check if file exists
if [ ! -f "$CONFIG_DIR/alertmanager.yml" ]; then
    echo "Config file not found at $CONFIG_DIR/alertmanager.yml"
    exit 1
fi

# Backup original
echo "Backing up original config..."
sudo cp "$CONFIG_DIR/alertmanager.yml" "$CONFIG_DIR/alertmanager.yml.backup.$(date +%s)"

# Fix the webhook URLs
echo "Fixing webhook URLs..."
sudo sed -i 's|/webhook/alerts|/api/alerts/webhook|g' "$CONFIG_DIR/alertmanager.yml"

# Verify the change
echo ""
echo "Verifying changes..."
grep "webhook_configs" -A 2 "$CONFIG_DIR/alertmanager.yml" | head -6

# Restart Alertmanager
echo ""
echo "Restarting Alertmanager..."
docker restart alertmanager

echo ""
echo "Done! Wait 5 seconds for Alertmanager to start..."
sleep 5

echo "Alertmanager should now be configured correctly!"
