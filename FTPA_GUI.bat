@echo off
setlocal
rem ============================================================
rem  FTPA GUI desktop launcher
rem  Double-click this file to start the GUI directly.
rem ============================================================

rem Switch to the project root directory
set "ROOT=%~dp0"
pushd "%ROOT%"

rem Prefer the project virtual environment Python, fall back to system Python
if exist "%ROOT%.venv\Scripts\python.exe" (
    set "PYTHON=%ROOT%.venv\Scripts\python.exe"
) else (
    set "PYTHON=python"
)

rem Ensure src is on the module search path
set "PYTHONPATH=%ROOT%src;%PYTHONPATH%"

echo Starting FTPA GUI ...
"%PYTHON%" -m ftpa.main %*

if errorlevel 1 (
    echo.
    echo Failed to start FTPA GUI. Check the error messages above.
    pause
)

popd
endlocal
