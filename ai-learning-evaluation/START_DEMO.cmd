@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto dependencies
where py >nul 2>nul
if errorlevel 1 goto usepython
py -3 -m venv .venv
if errorlevel 1 goto failed
goto dependencies
:usepython
python -m venv .venv
if errorlevel 1 goto failed
:dependencies
if exist ".venv\demo-ready.txt" goto launch
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto failed
echo Dependencies installed>".venv\demo-ready.txt"
:launch
".venv\Scripts\python.exe" app.py
if errorlevel 1 goto failed
exit /b 0
:failed
echo.
echo Setup or launch failed. Please send the error above to Heet.
echo Install Python 3.13 with Tcl/Tk support if Python is missing.
echo First-time setup needs an internet connection.
pause
exit /b 1
