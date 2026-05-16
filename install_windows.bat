@echo off
echo Setting up Ortho4XP...
echo:

where uv >nul 2>nul
if errorlevel 1 (
    echo Error: uv is required. Install it from https://docs.astral.sh/uv/
    pause
    exit /b 1
)

echo Creating and syncing the uv environment
uv sync --dev
echo:

echo Ortho4XP setup complete!
echo:

echo Use start_windows.bat to start Ortho4XP
echo:

pause
