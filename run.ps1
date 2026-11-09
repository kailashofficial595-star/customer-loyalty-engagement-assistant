$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$venvPython = Join-Path $scriptDir ".venv\Scripts\python.exe"

Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host " HCLTech Hackathon: Customer Loyalty and Engagement Assistant" -ForegroundColor Cyan
Write-Host "=================================================================" -ForegroundColor Cyan
Write-Host "Starting server at: http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "Interactive Swagger API Docs: http://127.0.0.1:8000/docs" -ForegroundColor Yellow

$env:PYTHONPATH = $scriptDir
& $venvPython (Join-Path $scriptDir "run_server.py")
