@echo off
REM ============================================================
REM  Build script — Virtual Projection Viewer v1.4
REM  Creates a standalone Windows .exe
REM ============================================================

echo.
echo === Building Virtual Projection Viewer ===
echo.

REM Clean previous build
if exist dist rmdir /s /q dist
if exist build rmdir /s /q build

REM Run PyInstaller
pyinstaller ^
    --name "VirtualProjectionViewer" ^
    --onedir ^
    --noconfirm ^
    --hidden-import moderngl ^
    --hidden-import glm ^
    --hidden-import numpy ^
    --hidden-import tkinter ^
    --hidden-import tkinter.filedialog ^
    --collect-all imgui_bundle ^
    --collect-all moderngl ^
    main.py

if errorlevel 1 (
    echo.
    echo === BUILD FAILED ===
    pause
    exit /b 1
)

REM Copy supporting files into dist
copy settings.py dist\VirtualProjectionViewer\ >nul 2>&1
copy camera.py dist\VirtualProjectionViewer\ >nul 2>&1
copy renderer.py dist\VirtualProjectionViewer\ >nul 2>&1
copy ndi_input.py dist\VirtualProjectionViewer\ >nul 2>&1
copy obj_loader.py dist\VirtualProjectionViewer\ >nul 2>&1

echo.
echo === Build complete ===
echo.
echo Output: dist\VirtualProjectionViewer\
echo Run:    dist\VirtualProjectionViewer\VirtualProjectionViewer.exe
echo.
echo Ship the entire dist\VirtualProjectionViewer folder to your client.
echo The NDI Runtime must be installed on the target machine:
echo   https://ndi.video/tools/
echo.
pause
