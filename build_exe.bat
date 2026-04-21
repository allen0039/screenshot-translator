@echo off
setlocal

cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
  echo [ERROR] 未找到虚拟环境 .venv
  echo 请先执行:
  echo   python -m venv .venv
  echo   .\.venv\Scripts\activate
  echo   pip install -r requirements.txt
  exit /b 1
)

call ".venv\Scripts\activate.bat"

echo [0/3] 检查 Python 版本...
python -c "import sys; raise SystemExit(0 if sys.version_info[:2] < (3,14) else 1)"
if errorlevel 1 (
  echo [ERROR] 当前 .venv 使用的是 Python 3.14，依赖不兼容，无法稳定打包。
  echo 请安装 Python 3.11 或 3.12 后重新创建虚拟环境：
  echo   rmdir /s /q .venv
  echo   py -3.12 -m venv .venv
  echo   .\.venv\Scripts\activate
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

echo [1/2] 安装打包工具...
pip install pyinstaller

echo [2/3] 检查关键依赖...
python -c "import keyboard, numpy, openai, PIL, rapidocr_onnxruntime, PySide6; print('OK')"
if errorlevel 1 (
  echo [ERROR] 关键依赖未安装完整，请执行：
  echo   pip install -r requirements.txt
  pause
  exit /b 1
)

echo [3/3] 开始打包...
pyinstaller --noconfirm --clean --windowed --name ScreenshotTranslator --collect-data rapidocr_onnxruntime main.py

echo.
echo 打包完成: dist\ScreenshotTranslator\ScreenshotTranslator.exe
pause
