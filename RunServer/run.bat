@echo off
cd /d "%~dp0..\Scripts\server"
python server.py
if errorlevel 1 pause