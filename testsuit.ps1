# Run with .\testsuit.ps1; arguments are forwarded unchanged to the Python CLI.
$suitePython = $env:TESTSUIT_PYTHON
if (-not $suitePython) {
    $projectPython = Join-Path $PSScriptRoot 'ai-learning-evaluation/.venv/Scripts/python.exe'
    if (Test-Path -LiteralPath $projectPython) { $suitePython = $projectPython }
    else { $suitePython = 'python' }
}
& $suitePython (Join-Path $PSScriptRoot 'tools/testsuit.py') @args
exit $LASTEXITCODE
