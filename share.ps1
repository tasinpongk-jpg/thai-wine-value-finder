# Thai Wine Value Finder — put it online with a free Cloudflare link.
# Keep this window OPEN while you want the site reachable. Close it to take it offline.
$ErrorActionPreference = "SilentlyContinue"
Set-Location $PSScriptRoot

$cloudflared = "$env:USERPROFILE\.cloudflared\cloudflared.exe"

# 1) Start the dashboard if it isn't already running on port 8501
$running = Test-NetConnection -ComputerName localhost -Port 8501 -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $running) {
    Write-Host "Starting the wine dashboard..." -ForegroundColor Cyan
    Start-Process -WindowStyle Minimized python -ArgumentList `
        "-m","streamlit","run","dashboard.py","--server.port=8501","--server.headless=true"
    Start-Sleep -Seconds 9
} else {
    Write-Host "Dashboard already running." -ForegroundColor DarkGray
}

# 2) Open the free Cloudflare tunnel. It prints a https://...trycloudflare.com link.
Write-Host ""
Write-Host "Opening your Cloudflare link below. Copy the https://...trycloudflare.com address." -ForegroundColor Green
Write-Host "(The link is new each time you run this. Keep this window open to stay online.)" -ForegroundColor Yellow
Write-Host ""
& $cloudflared tunnel --url http://localhost:8501
