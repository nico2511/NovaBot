#!/usr/bin/env pwsh
# Log Rotation Script for NovaBot
# Keeps only the last 2 days of logs to prevent disk space issues

$LogDir = "logs"
$RetentionDays = 2
$Now = Get-Date

Write-Host "🧹 Starting log cleanup (retention: $RetentionDays days)..." -ForegroundColor Cyan

# Get all log files older than retention period
$OldLogs = Get-ChildItem -Path $LogDir -Filter "*.log" | Where-Object {
    $_.LastWriteTime -lt $Now.AddDays(-$RetentionDays)
}

if ($OldLogs.Count -eq 0) {
    Write-Host "✅ No old logs to clean up" -ForegroundColor Green
    exit 0
}

Write-Host "📋 Found $($OldLogs.Count) log file(s) older than $RetentionDays days:" -ForegroundColor Yellow

foreach ($Log in $OldLogs) {
    $Age = ($Now - $Log.LastWriteTime).Days
    $SizeMB = [math]::Round($Log.Length / 1MB, 2)
    Write-Host "  - $($Log.Name) (Age: $Age days, Size: $SizeMB MB)" -ForegroundColor Gray
}

# Confirm deletion
$Confirm = Read-Host "Delete these files? (y/N)"
if ($Confirm -ne 'y') {
    Write-Host "❌ Cleanup cancelled" -ForegroundColor Red
    exit 1
}

# Delete old logs
$DeletedCount = 0
$FreedSpace = 0

foreach ($Log in $OldLogs) {
    try {
        $FreedSpace += $Log.Length
        Remove-Item $Log.FullName -Force
        Write-Host "  ✅ Deleted: $($Log.Name)" -ForegroundColor Green
        $DeletedCount++
    } catch {
        Write-Host "  ❌ Failed to delete: $($Log.Name) - $($_.Exception.Message)" -ForegroundColor Red
    }
}

$FreedSpaceMB = [math]::Round($FreedSpace / 1MB, 2)
Write-Host "`n✅ Cleanup complete: Deleted $DeletedCount file(s), freed $FreedSpaceMB MB" -ForegroundColor Green
