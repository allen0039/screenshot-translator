@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] Missing virtual environment: .venv
  echo Please run:
  echo   python -m venv .venv
  echo   .\.venv\Scripts\activate
  echo   pip install -r requirements.txt
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo [0/3] Checking Python version...
python -c "import sys; raise SystemExit(0 if sys.version_info[:2] < (3,14) else 1)"
if errorlevel 1 (
  echo [ERROR] Python 3.14+ is not supported for this build.
  echo Recreate .venv with Python 3.11 or 3.12:
  echo   rmdir /s /q .venv
  echo   py -3.12 -m venv .venv
  echo   .\.venv\Scripts\activate
  echo   pip install -r requirements.txt
  if not "%NO_PAUSE%"=="1" pause
  exit /b 1
)

echo [1/3] Installing build tool...
pip install pyinstaller

echo [2/3] Verifying dependencies...
python -c "import keyboard, numpy, openai, PIL, rapidocr_onnxruntime, PySide6; print('OK')"
if errorlevel 1 (
  echo [ERROR] Missing required dependencies.
  echo Run: pip install -r requirements.txt
  if not "%NO_PAUSE%"=="1" pause
  exit /b 1
)

echo [3/3] Building onefile EXE...
pyinstaller --noconfirm --clean --windowed --onefile --noupx --name ScreenshotTranslator-OneFile --collect-data rapidocr_onnxruntime main.py
if errorlevel 1 (
  echo [ERROR] onefile build failed.
  if not "%NO_PAUSE%"=="1" pause
  exit /b 1
)

echo.
echo Build done: dist\ScreenshotTranslator-OneFile.exe
if not "%NO_PAUSE%"=="1" pause
