@echo off
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo.
echo  =============================================
echo    INVOICE GENERATOR - Windows Build Script
echo  =============================================
echo.
echo  This creates a portable app for your colleague.
echo  Takes about 2-3 minutes. No installation needed.
echo.
echo  Press any key to start...
pause >nul

echo.
echo [1/6] Downloading Python (embedded)...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://www.python.org/ftp/python/3.11.7/python-3.11.7-embed-amd64.zip' -OutFile 'python.zip'"
if not exist "python.zip" (
    echo ERROR: Failed to download Python. Check internet connection.
    pause
    exit /b 1
)

echo [2/6] Downloading Tesseract OCR...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://digi.bib.uni-mannheim.de/tesseract/tesseract-ocr-w64-setup-5.3.1.20230401.exe' -OutFile 'tesseract_setup.exe'" 2>nul
if not exist "tesseract_setup.exe" (
    echo First source failed, trying alternative...
    powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; $ProgressPreference = 'SilentlyContinue'; Invoke-WebRequest -Uri 'https://github.com/UB-Mannheim/tesseract/releases/download/v5.3.1.20230401/tesseract-ocr-w64-setup-v5.3.1.20230401.exe' -OutFile 'tesseract_setup.exe'" 2>nul
)
if not exist "tesseract_setup.exe" (
    echo.
    echo Could not auto-download Tesseract.
    echo Please download manually from:
    echo https://github.com/UB-Mannheim/tesseract/wiki
    echo.
    echo Save the installer as "tesseract_setup.exe" in this folder
    echo Then run BUILD.bat again.
    echo.
    pause
    exit /b 1
)

echo [3/6] Downloading pip...
powershell -Command "[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12; Invoke-WebRequest -Uri 'https://bootstrap.pypa.io/get-pip.py' -OutFile 'get-pip.py'"

echo [4/6] Setting up portable folder...
mkdir "InvoiceGenerator" 2>nul
powershell -Command "Expand-Archive -Path 'python.zip' -DestinationPath 'InvoiceGenerator\python' -Force"

REM Enable imports in embedded Python
echo Lib\site-packages>> "InvoiceGenerator\python\python311._pth"

REM Install pip and packages
echo [5/6] Installing Python packages (this takes a minute)...
"InvoiceGenerator\python\python.exe" get-pip.py --no-warn-script-location >nul 2>&1
"InvoiceGenerator\python\python.exe" -m pip install pytesseract Pillow pypdf reportlab --no-warn-script-location --quiet

REM Copy app files
echo [6/6] Copying app files...
copy "invoice_app_windows.py" "InvoiceGenerator\" >nul
copy "generate_invoice.py" "InvoiceGenerator\" >nul
xcopy "utils" "InvoiceGenerator\utils\" /E /I /Q >nul
xcopy "templates" "InvoiceGenerator\templates\" /E /I /Q >nul
mkdir "InvoiceGenerator\output" 2>nul

REM Install Tesseract
echo.
echo  =============================================
echo    TESSERACT INSTALLATION
echo  =============================================
echo.
echo  The Tesseract installer will now open.
echo.
echo  IMPORTANT: When asked for install location, use:
echo  %CD%\InvoiceGenerator\tesseract
echo.
echo  Press any key to open the installer...
pause >nul

start /wait tesseract_setup.exe /S /D=%CD%\InvoiceGenerator\tesseract

REM Create launcher
(
echo @echo off
echo cd /d "%%~dp0"
echo set "PATH=%%CD%%\tesseract;%%CD%%\python;%%PATH%%"
echo set "TESSDATA_PREFIX=%%CD%%\tesseract\tessdata"
echo start "" python\pythonw.exe invoice_app_windows.py
) > "InvoiceGenerator\Invoice Generator.bat"

REM Cleanup
del python.zip 2>nul
del tesseract_setup.exe 2>nul
del get-pip.py 2>nul

echo.
echo  =============================================
echo    BUILD COMPLETE!
echo  =============================================
echo.
echo  Your portable app is ready in: InvoiceGenerator
echo.
echo  TO SEND TO YOUR COLLEAGUE:
echo  1. Zip the entire "InvoiceGenerator" folder
echo  2. Send the zip file
echo  3. They extract and double-click "Invoice Generator.bat"
echo.
echo  Press any key to test the app now...
pause >nul

cd InvoiceGenerator
call "Invoice Generator.bat"
