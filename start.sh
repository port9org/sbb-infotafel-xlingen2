#!/bin/bash
set -euo pipefail

cd "$(dirname "$0")"

echo "Stopping old processes..."
pkill -f "python3 -m http.server 8080" || true
pkill -f "python3.*capture\.py"        || true
pkill -f "python3.*display_infotafel"  || true
sleep 1

echo "1. Starting file server on :8080..."
nohup python3 -m http.server 8080 </dev/null >/tmp/http.log 2>&1 &

echo "2. Starting capture loop..."
nohup python3 -u capture.py </dev/null >/tmp/capture.log 2>&1 &

echo "3. Starting e-paper display..."
if [ "$(uname -s)" = "Linux" ]; then
    sudo python3 -u display_infotafel.py >/tmp/display.log 2>&1 &
else
    python3 -u display_infotafel.py >/tmp/display.log 2>&1 &
fi

echo ""
echo "All processes started."
echo "  tail -f /tmp/capture.log   — capture pipeline"
echo "  tail -f /tmp/display.log   — e-paper driver"
echo "  tail -f /tmp/http.log      — file server"
