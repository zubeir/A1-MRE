# Script to copy the trading codebase to network folder
# Source: Current directory
# Destination: Z:\top10_sp_momentum

$SourceDir = Get-Location
$DestinationDir = "Z:\top10_sp_momentum"

Write-Host "Starting copy from $SourceDir to $DestinationDir" -ForegroundColor Green

# Check if destination exists, create if not
if (-not (Test-Path $DestinationDir)) {
    Write-Host "Creating destination directory: $DestinationDir" -ForegroundColor Yellow
    New-Item -ItemType Directory -Path $DestinationDir -Force
}

# Exclude patterns for files/folders we don't want to copy
$excludePatterns = @(
    "*.log",
    ".git",
    ".venv", 
    "__pycache__",
    ".streamlit",
    "uploads",
    "cache.json",
    "conversation.log",
    "agent.err.log",
    "streamlit.err.log",
    "steps done.docx",
    "*.tmp"
)

Write-Host "Copying files (excluding logs, cache, and temporary files)..." -ForegroundColor Yellow

# Use robocopy for reliable copying with retry and exclude patterns
$excludeDirs = @("/XD", ".git", ".venv", "__pycache__", ".streamlit", "uploads")
$excludeFiles = @("/XF", "*.log", "*.tmp", "cache.json", "conversation.log", "agent.err.log", "streamlit.err.log", "steps done.docx")

$robocopyArgs = @(
    $SourceDir,
    $DestinationDir,
    "/E",           # Copy subdirectories, including empty ones
    "/COPY:DAT",    # Copy Data, Attributes, Timestamps
    "/R:3",         # Retry 3 times
    "/W:5",         # Wait 5 seconds between retries
    "/TEE",         # Output to console window and log file
    "/NFL",         # No file list
    "/NDL",         # No directory list
    "/NJH",         # No job header
    "/NJS",         # No job summary
    "/NC",          # No file class
    "/NS",          # No file size
    "/NP"           # No progress
) + $excludeDirs + $excludeFiles

try {
    & robocopy @robocopyArgs
    
    if ($LASTEXITCODE -lt 8) {
        Write-Host "Copy completed successfully!" -ForegroundColor Green
        Write-Host "Files copied to: $DestinationDir" -ForegroundColor Cyan
    } else {
        Write-Host "Copy completed with some issues. Exit code: $LASTEXITCODE" -ForegroundColor Yellow
    }
} catch {
    Write-Host "Error during copy: $_" -ForegroundColor Red
    exit 1
}

# Show what was copied
Write-Host "`nVerifying copied files..." -ForegroundColor Yellow
if (Test-Path $DestinationDir) {
    $copiedFiles = Get-ChildItem -Path $DestinationDir -Recurse | Measure-Object
    Write-Host "Total items copied: $($copiedFiles.Count)" -ForegroundColor Green
} else {
    Write-Host "Destination not found after copy!" -ForegroundColor Red
}
