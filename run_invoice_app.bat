@echo off
echo Starting Invoice Generator...
python invoice_app_windows.py
if errorlevel 1 (
    echo.
    echo Error: Make sure Python is installed and added to PATH
    echo See WINDOWS_SETUP.txt for installation instructions
    pause
)
