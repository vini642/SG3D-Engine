@echo off
cd /d "%~dp0"
python tools\project_export.py examples\modular_mini_golf\MiniGolf_Modular.sg3d.json
if errorlevel 1 goto fail
python build.py --main generated/main.c --output build\SG3D_Modular_MiniGolf.gba
if errorlevel 1 goto fail
echo.
echo GBA ROM ready: build\SG3D_Modular_MiniGolf.gba
pause
exit /b 0
:fail
echo.
echo Build failed. Check that Python, Pillow, and devkitARM or clang/lld/llvm-objcopy are available.
pause
exit /b 1
