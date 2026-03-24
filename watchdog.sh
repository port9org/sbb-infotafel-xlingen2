#!/bin/bash
# Watchdog: restart if sbb.png hasn't been updated in 3 minutes.
# Run via cron every minute: * * * * * /path/to/watchdog.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SCREENSHOT="${REPO_DIR}/sbb.png"
HEARTBEAT="/tmp/display_heartbeat"
MAX_AGE=180  # seconds

if [ ! -f "$SCREENSHOT" ]; then
    echo "$(date '+%H:%M:%S') watchdog: no screenshot yet, restarting"
    exec "${REPO_DIR}/start.sh"
fi

age=$(( $(date +%s) - $(stat -c %Y "$SCREENSHOT" 2>/dev/null || stat -f %m "$SCREENSHOT") ))

if [ "$age" -gt "$MAX_AGE" ]; then
    echo "$(date '+%H:%M:%S') watchdog: screenshot ${age}s old (>${MAX_AGE}s), restarting"
    exec "${REPO_DIR}/start.sh"
fi

if [ ! -f "$HEARTBEAT" ]; then
    echo "$(date '+%H:%M:%S') watchdog: no display heartbeat yet, waiting"
    exit 0
fi

hb_age=$(( $(date +%s) - $(stat -c %Y "$HEARTBEAT" 2>/dev/null || stat -f %m "$HEARTBEAT") ))

if [ "$hb_age" -gt "$MAX_AGE" ]; then
    echo "$(date '+%H:%M:%S') watchdog: display heartbeat ${hb_age}s old (>${MAX_AGE}s), restarting"
    exec "${REPO_DIR}/start.sh"
fi
