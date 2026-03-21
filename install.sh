#!/bin/bash
# Run once on the Raspberry Pi to install dependencies and configure the system.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== SBB Infotafel install ==="

# ── Dependencies ─────────────────────────────────────────────
echo "Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y chromium-browser python3-pil python3-websocket

# ── Nightly reboot at 03:00 ──────────────────────────────────
echo "Setting up nightly reboot at 03:00..."
echo "0 3 * * * root /sbin/reboot" | sudo tee /etc/cron.d/sbb-infotafel-reboot > /dev/null
sudo chmod 644 /etc/cron.d/sbb-infotafel-reboot
echo "  → /etc/cron.d/sbb-infotafel-reboot written"

# ── Autostart on boot ────────────────────────────────────────
echo "Setting up autostart..."
CRON_LINE="@reboot sleep 15 && ${REPO_DIR}/start.sh"
( crontab -l 2>/dev/null | grep -v "sbb-infotafel"; echo "# sbb-infotafel autostart"; echo "${CRON_LINE}" ) | crontab -
echo "  → @reboot entry added to user crontab"

echo ""
echo "Done. Reboot the Pi to verify autostart."
echo "Logs: tail -f /tmp/capture.log /tmp/display.log"
