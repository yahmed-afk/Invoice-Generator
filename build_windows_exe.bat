@echo off
echo ============================================
echo   Building Invoice Generator for Windows
echo ============================================
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo [1/4] Installing build dependencies...
pip install pyinstaller pytesseract Pillow pypdf reportlab --quiet

echo [2/4] Downloading portable Tesseract OCR...
if not exist "tesseract" (
    echo Downloading Tesseract...
    powershell -Command "Invoke-WebRequest -Uri 'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.3.20231005.exe' -OutFile 'tesseract_setup.exe'"
    echo.
    echo IMPORTANT: Tesseract installer will open.
    echo Install it to: %CD%\tesseract
    echo Then press any key to continue...
    start /wait tesseract_setup.exe
    pause
)

echo [3/4] Creating executable...
pyinstaller --noconfirm --onefile --windowed ^
    --name "InvoiceGenerator" ^
    --add-data "templates;templates" ^
    --add-data "utils;utils" ^
    --hidden-import PIL ^
    --hidden-import pytesseract ^
    invoice_app_windows.py

echo [4/4] Copying required files...
if not exist "dist\templates" mkdir "dist\templates"
if not exist "dist\output" mkdir "dist\output"
copy "templates\blank template.pdf" "dist\templates\"

echo.
echo ============================================
echo   BUILD COMPLETE!
echo ============================================
echo.
echo Your executable is at: dist\InvoiceGenerator.exe
echo.
echo To distribute, zip the entire 'dist' folder.
echo.
pause
