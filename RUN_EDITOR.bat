@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 editor\visual_editor.py
) else (
  python editor\visual_editor.py
)
if errorlevel 1 (
  echo.
  echo Editor failed. Install Python 3. For PNG export, run: python -m pip install Pillow
  pause
)
