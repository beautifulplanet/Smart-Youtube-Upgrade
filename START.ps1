# YouTube Safety Inspector - Easy Setup
# Just run this script and paste your API key when asked

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  YouTube Safety Inspector Setup" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Ask for API key
Write-Host "Paste your YouTube API key and press Enter:" -ForegroundColor Yellow
$apiKey = Read-Host

if ($apiKey -eq "" -or $apiKey.Length -lt 20) {
    Write-Host "Invalid key. Please try again." -ForegroundColor Red
    exit
}

# Set it for this session
$env:YOUTUBE_API_KEY = $apiKey

Write-Host ""
Write-Host "API Key set!" -ForegroundColor Green
Write-Host ""
Write-Host "Starting server..." -ForegroundColor Yellow
Write-Host ""

# Start the server
Set-Location "$PSScriptRoot\backend"
python main.py
