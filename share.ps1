# Thai Wine Value Finder — share a READ-ONLY copy with a free Cloudflare link.
# Keep this window OPEN while you want the site reachable. Close it to take it offline.
$ErrorActionPreference = "SilentlyContinue"
Set-Location $PSScriptRoot

$cloudflared = "$env:USERPROFILE\.cloudflared\cloudflared.exe"

# 1) Start a separate READ-ONLY copy of the dashboard on port 8502 for sharing.
#    WINEVALUE_PUBLIC_MODE=1 hides "My Cellar" and every cellar write, so anyone
#    with the link can browse wines but can't see or change your purchases.
#    (Your normal local dashboard on 8501, if running, is NOT exposed.)
#    To share the cellar with yourself instead, set a cellar password (see README)
#    and run Streamlit manually.
$port = 8502
$running = Test-NetConnection -ComputerName localhost -Port $port -InformationLevel Quiet -WarningAction SilentlyContinue
if (-not $running) {
    Write-Host "Starting a read-only wine dashboard for sharing..." -ForegroundColor Cyan
    $env:WINEVALUE_PUBLIC_MODE = "1"
    Start-Process -WindowStyle Minimized python -ArgumentList `
        "-m","streamlit","run","dashboard.py","--server.port=$port","--server.headless=true"
    Start-Sleep -Seconds 9
} else {
    Write-Host "Read-only dashboard already running on port $port." -ForegroundColor DarkGray
}

# 2) Open the free Cloudflare tunnel. It prints a https://...trycloudflare.com link.
Write-Host ""
Write-Host "Opening your Cloudflare link below. Copy the https://...trycloudflare.com address." -ForegroundColor Green
Write-Host "(The link is new each time you run this. Keep this window open to stay online.)" -ForegroundColor Yellow
Write-Host ""
& $cloudflared tunnel --url http://localhost:$port
