@echo off
cd /d "%~dp0"
py -m pip install -r requirements.txt
if errorlevel 1 goto error
py viewer.py
if errorlevel 1 goto error
exit /b 0
:error
echo Launch failed. Make sure Python 3 is installed.
pause
exit /b 1
