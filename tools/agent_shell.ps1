# Resident elevated runner - one UAC approval, then executes command files in order.
# Origin: map_search tools/agent_shell.ps1 (ported 2026-08-09; ASCII-only to avoid
#         PS5.1 encoding issues with non-BOM UTF-8 scripts).
# Protocol: cmd_NNNN.txt (PowerShell script) -> res_NNNN.log (output) + done_NNNN.txt (exit code)
param([string]$Dir, [double]$IdleQuitMin = 300)

Set-Location (Split-Path $PSScriptRoot -Parent)
$env:PYTHONIOENCODING = 'utf-8'
if (-not $Dir) { $Dir = Join-Path (Get-Location) 'output\agent_shell' }
New-Item -ItemType Directory -Force $Dir | Out-Null
$elev = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
"start $(Get-Date -Format o) pid=$PID elevated=$elev cwd=$(Get-Location)" | Out-File "$Dir\shell_status.txt" -Encoding utf8 -Append

$seq = 1
$last = Get-Date
while (((Get-Date) - $last).TotalMinutes -lt $IdleQuitMin) {
    $cf = Join-Path $Dir ("cmd_{0:D4}.txt" -f $seq)
    if (-not (Test-Path $cf)) { Start-Sleep -Milliseconds 300; continue }
    Start-Sleep -Milliseconds 200
    $last = Get-Date
    $res = Join-Path $Dir ("res_{0:D4}.log" -f $seq)
    $done = Join-Path $Dir ("done_{0:D4}.txt" -f $seq)
    $body = Get-Content $cf -Raw -Encoding utf8
    "run #$seq $(Get-Date -Format o)" | Out-File "$Dir\shell_status.txt" -Encoding utf8 -Append
    if ($body.Trim() -eq 'quit') { 'quit' | Out-File $done -Encoding utf8; break }
    $tmp = Join-Path $Dir ("run_{0:D4}.ps1" -f $seq)
    $body | Out-File $tmp -Encoding utf8
    & powershell -NoProfile -ExecutionPolicy Bypass -File $tmp > $res 2>&1
    "$LASTEXITCODE" | Out-File $done -Encoding utf8
    $seq += 1
}
"exit $(Get-Date -Format o)" | Out-File "$Dir\shell_status.txt" -Encoding utf8 -Append
