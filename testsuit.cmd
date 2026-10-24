@echo off
setlocal
set "SUITE_PYTHON=%TESTSUIT_PYTHON%"
if defined SUITE_PYTHON goto run
set "SUITE_PYTHON=%~dp0ai-learning-evaluation\.venv\Scripts\python.exe"
if exist "%SUITE_PYTHON%" goto run
set "SUITE_PYTHON=python"
:run
"%SUITE_PYTHON%" "%~dp0tools\testsuit.py" %*
exit /b %errorlevel%
