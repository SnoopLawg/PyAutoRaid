@echo off
REM Run the 6-star autonomous farm-and-rank-up loop.
REM Usage:
REM   six_star.cmd Harima
REM   six_star.cmd            (prompts for hero name)
REM
REM Double-clickable from Explorer. Closes loop when done or Ctrl-C.
REM Logs both to console and farm_<hero>.log so you can review later.

setlocal
cd /d "%~dp0"

set HERO=%~1
if "%HERO%"=="" (
    set /p HERO=Hero to 6-star:
)
if "%HERO%"=="" (
    echo No hero specified. Aborting.
    pause
    exit /b 1
)

set LOGFILE=farm_%HERO%.log
echo ===============================================
echo  PyAutoRaid - 6-star %HERO%
echo  log: %LOGFILE%
echo  press Ctrl-C to stop
echo ===============================================
echo.

REM -u = unbuffered so the log + console update live
python -u tools\six_star.py "%HERO%" 2>&1 | powershell -NoProfile -Command "$input | Tee-Object -FilePath '%LOGFILE%' -Append"

echo.
echo === Loop ended. Log saved to %LOGFILE% ===
pause
