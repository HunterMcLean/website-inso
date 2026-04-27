@echo off
REM Double-click to launch a local server and open the library.
cd /d "%~dp0"
start "" http://localhost:8765/
python -m http.server 8765
