@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (set PYTHON=py -3) else (set PYTHON=python)
%PYTHON% tools\project_export.py examples\collectathon_v12.sg3d.json
if errorlevel 1 goto error
%PYTHON% build.py --main generated/main.c --output build/SG3D_1_0_Collectathon.gba
if errorlevel 1 goto error
echo SG3D Studio 1.0 collectathon/HUD demo ROM: build\SG3D_1_0_Collectathon.gba
pause
exit /b 0
:error
echo Export/build failed. Install Python/Pillow and an ARM toolchain.
pause
exit /b 1
