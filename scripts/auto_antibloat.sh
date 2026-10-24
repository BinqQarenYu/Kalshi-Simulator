#!/usr/bin/env bash
# ==============================================================================
# AWS EC2 Anti-Bloat Autonomous Maintenance Daemon
# Target: /home/ec2-user/kalshi-bot/scripts/auto_antibloat.sh
# Purpose: Prevent journal log explosion, stale tick dumps, RAM cache buildup,
#          and database fragmentation without disrupting live trading engines.
# ==============================================================================

set -euo pipefail

REPO_DIR="/home/ec2-user/kalshi-bot"
LOG_TAG="[ANTI-BLOAT]"

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') $LOG_TAG Starting autonomous anti-bloat pass..."

# 1. Vacuum Systemd Journal Logs (cap total journal size to 50M)
echo "$LOG_TAG Vacuuming systemd journal logs to <= 50MB..."
sudo journalctl --vacuum-size=50M --vacuum-time=3d > /dev/null 2>&1 || true

# 2. Clean temporary /tmp buffers older than 1 day
echo "$LOG_TAG Cleaning stale /tmp buffers..."
find /tmp -maxdepth 1 -type f -name 'tmp*' -mtime +1 -delete 2>/dev/null || true

# 3. Clean stale tick streams and orphan JSONL dumps in data/
if [ -d "$REPO_DIR/data" ]; then
    echo "$LOG_TAG Removing stale uncompressed stream_*.jsonl files older than 6 hours..."
    find "$REPO_DIR/data" -maxdepth 1 -name "stream_*.jsonl" -mmin +360 -delete 2>/dev/null || true
fi

# 4. Clean Python __pycache__ and .pyc bytecode
echo "$LOG_TAG Cleaning recursive Python bytecode caches..."
find "$REPO_DIR" -name "*.pyc" -delete 2>/dev/null || true
find "$REPO_DIR" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

# 5. Flush Linux Page Cache & Inode Dentries (Free up inactive RAM for bots)
echo "$LOG_TAG Synchronizing disks and dropping page caches..."
sync
echo 3 | sudo tee /proc/sys/vm/drop_caches > /dev/null

echo "$(date -u +'%Y-%m-%dT%H:%M:%SZ') $LOG_TAG Anti-bloat pass complete. Current Disk & Memory status:"
df -h / | tail -n 1
free -m | grep -E "Mem:|Swap:"
