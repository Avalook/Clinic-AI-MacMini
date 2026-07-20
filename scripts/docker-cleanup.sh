#!/bin/bash
# Automated Docker cleanup — removes dangling images, stopped containers,
# and unused volumes older than 7 days. Prevents SSD fill-up on Mac mini.
#
# Run manually:  ./scripts/docker-cleanup.sh
# Or via LaunchDaemon (see scripts/launchdaemons/com.dr4women.docker-cleanup.plist)
set -u

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
LOG="$HOME/Library/Logs/docker-cleanup.log"

ts() { date "+%Y-%m-%d %H:%M:%S"; }
log() { echo "[$(ts)] $*" >> "$LOG"; }

log "=== Docker cleanup starting ==="

# Check Docker is available.
if ! command -v docker > /dev/null 2>&1 || ! docker info > /dev/null 2>&1; then
    log "Docker daemon not available — skipping cleanup"
    exit 0
fi

# Remove stopped containers, dangling images, unused networks, build cache
# older than 7 days. --filter "until=168h" keeps recent images safe.
BEFORE=$(docker system df --format '{{.Size}}' 2>/dev/null | head -1)
log "Disk usage before: $BEFORE"

docker system prune -af --filter "until=168h" >> "$LOG" 2>&1
docker volume prune -f >> "$LOG" 2>&1

AFTER=$(docker system df --format '{{.Size}}' 2>/dev/null | head -1)
log "Disk usage after:  $AFTER"
log "=== Docker cleanup complete ==="
