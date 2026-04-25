@echo off
setlocal

cd /d "%~dp0"
set "NO_PAUSE=1"

call "%~dp0build_exe.bat"
if errorlevel 1 (
  echo [ERROR] onedir build failed.
  exit /b 1
)

call "%~dp0build_onefile.bat"
if errorlevel 1 (
  echo [ERROR] onefile build failed.
  exit /b 1
)

set "ISCC_EXE=C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
if not exist "%ISCC_EXE%" (
  set "ISCC_EXE=C:\Program Files\Inno Setup 6\ISCC.exe"
)
if not exist "%ISCC_EXE%" (
  set "ISCC_EXE=%LOCALAPPDATA%\Programs\Inno Setup 6\ISCC.exe"
)

if not exist "%ISCC_EXE%" (
  echo [WARN] Inno Setup ISCC.exe not found. Skipping installer build.
  echo [WARN] Install Inno Setup 6 and run again:
  echo [WARN] https://jrsoftware.org/isdl.php
  exit /b 0
)

echo [installer] Building installer EXE...
"%ISCC_EXE%" installer.iss
if errorlevel 1 (
  echo [ERROR] installer build failed.
  exit /b 1
)

echo.
echo Release artifacts:
if exist "dist\ScreenshotTranslator\ScreenshotTranslator.exe" echo - onedir: dist\ScreenshotTranslator\ScreenshotTranslator.exe
if exist "dist\ScreenshotTranslator-OneFile.exe" echo - onefile: dist\ScreenshotTranslator-OneFile.exe
for %%F in (dist\ScreenshotTranslator-Setup-*.exe) do echo - installer: %%F
