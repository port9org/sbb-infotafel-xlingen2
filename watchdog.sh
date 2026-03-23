#!/bin/bash
# Watchdog: restart if sbb.png hasn't been updated in 3 minutes.
# Run via cron every minute: * * * * * /path/to/watchdog.sh
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
SCREENSHOT="${REPO_DIR}/sbb.png"
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
