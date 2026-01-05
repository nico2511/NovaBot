#!/bin/bash
# Log Rotation Script for NovaBot (Linux/Production)
# Keeps only the last 2 days of logs to prevent disk space issues

LOG_DIR="logs"
RETENTION_DAYS=2

echo "🧹 Starting log cleanup (retention: ${RETENTION_DAYS} days)..."

# Find and delete logs older than retention period
DELETED_COUNT=0
FREED_SPACE=0

while IFS= read -r -d '' log_file; do
    file_size=$(stat -f%z "$log_file" 2>/dev/null || stat -c%s "$log_file" 2>/dev/null)
    file_age=$(( ( $(date +%s) - $(stat -f%m "$log_file" 2>/dev/null || stat -c%Y "$log_file" 2>/dev/null) ) / 86400 ))
    
    echo "  - Deleting: $(basename "$log_file") (Age: ${file_age} days, Size: $((file_size / 1024 / 1024)) MB)"
    
    rm -f "$log_file"
    DELETED_COUNT=$((DELETED_COUNT + 1))
    FREED_SPACE=$((FREED_SPACE + file_size))
done < <(find "$LOG_DIR" -name "*.log" -type f -mtime +$RETENTION_DAYS -print0)

if [ $DELETED_COUNT -eq 0 ]; then
    echo "✅ No old logs to clean up"
else
    FREED_MB=$((FREED_SPACE / 1024 / 1024))
    echo "✅ Cleanup complete: Deleted $DELETED_COUNT file(s), freed ${FREED_MB} MB"
fi
