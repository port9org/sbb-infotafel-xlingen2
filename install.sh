#!/bin/bash
# Run once on the Raspberry Pi to install dependencies and configure the system.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== SBB Infotafel install ==="

# ── Dependencies ─────────────────────────────────────────────
echo "Installing system packages..."
sudo apt-get update -q
sudo apt-get install -y chromium chromium-driver python3-pil python3-selenium || \
sudo apt-get install -y chromium-browser chromium-driver python3-pil python3-selenium

# ── NTP time sync (every 10 minutes + on boot) ──────────────
echo "Configuring NTP time sync..."
sudo timedatectl set-ntp true
sudo mkdir -p /etc/systemd/timesyncd.conf.d
cat << 'CONF' | sudo tee /etc/systemd/timesyncd.conf.d/frequent.conf > /dev/null
[Time]
NTP=pool.ntp.org
PollIntervalMinSec=600
PollIntervalMaxSec=600
CONF
sudo systemctl restart systemd-timesyncd
echo "  → NTP syncs every 10 minutes + on boot"

# ── Nightly reboot at 03:00 ──────────────────────────────────
echo "Setting up nightly reboot at 03:00..."
echo "0 3 * * * root /sbin/reboot" | sudo tee /etc/cron.d/sbb-infotafel-reboot > /dev/null
sudo chmod 644 /etc/cron.d/sbb-infotafel-reboot
echo "  → /etc/cron.d/sbb-infotafel-reboot written"

# ── Autostart on boot ────────────────────────────────────────
echo "Setting up autostart..."
chmod +x "${REPO_DIR}/start.sh" "${REPO_DIR}/watchdog.sh"
(
  crontab -l 2>/dev/null | grep -v "sbb-infotafel"
  echo "# sbb-infotafel autostart"
  echo "@reboot sleep 15 && sudo ${REPO_DIR}/start.sh"
) | crontab -
echo "  → @reboot cron entry added"

# ── Watchdog (every minute) ──────────────────────────────────
echo "Setting up watchdog..."
echo "* * * * * root ${REPO_DIR}/watchdog.sh >>/tmp/watchdog.log 2>&1" \
  | sudo tee /etc/cron.d/sbb-infotafel-watchdog > /dev/null
sudo chmod 644 /etc/cron.d/sbb-infotafel-watchdog
echo "  → /etc/cron.d/sbb-infotafel-watchdog written"

echo ""
echo "Done. Reboot the Pi to verify autostart."
echo "Logs: tail -f /tmp/capture.log /tmp/display.log"
