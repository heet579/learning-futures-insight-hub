param([switch]$SkipInstall)
$ErrorActionPreference = 'Stop'
$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location -LiteralPath $ProjectDir
if (-not (Test-Path -LiteralPath '.venv')) { python -m venv .venv }
& '.\.venv\Scripts\python.exe' -m pip install --upgrade pip
if (-not $SkipInstall) { & '.\.venv\Scripts\python.exe' -m pip install -r requirements.txt }
& '.\.venv\Scripts\python.exe' app.py


