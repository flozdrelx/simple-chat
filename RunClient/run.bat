@echo off
cd /d "%~dp0..\Scripts\client"
python client.py
if errorlevel 1 pause