Write-Host "========================================================" -ForegroundColor Cyan
Write-Host "   Stopping AI Smart Home Services (Backend + Frontend) " -ForegroundColor Cyan
Write-Host "========================================================" -ForegroundColor Cyan

$connections = Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue
if ($connections) {
    $pids = $connections | Select-Object -ExpandProperty OwningProcess -Unique
    foreach ($procId in $pids) {
        try {
            Stop-Process -Id $procId -Force -ErrorAction SilentlyContinue
            Write-Host "Stopped process ID $procId" -ForegroundColor Green
        } catch {
            Write-Host "Could not stop PID $procId" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "No active processes found on ports 8000 or 5173." -ForegroundColor Gray
}

Write-Host "Done!" -ForegroundColor Green
