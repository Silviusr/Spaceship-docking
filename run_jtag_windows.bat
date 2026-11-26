@echo off
cd /d "%~dp0"
py jtag_viewer.py
if errorlevel 1 pause
