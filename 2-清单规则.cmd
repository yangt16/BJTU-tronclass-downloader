@echo off
REM ===========================================================
REM  Configure per-course download rules.
REM  Double-click, pick a course, pick a rule. No rule = all.
REM
REM  HARD RULES: ASCII only, no angle brackets in comments, CRLF.
REM ===========================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

set "PYEXE="
if exist "%~dp0python\python.exe" call :trypy "%~dp0python\python.exe"
if defined PYEXE goto havepy
for /f "delims=" %%P in ('where python 2^>nul') do if not defined PYEXE call :trypy "%%P"
if defined PYEXE goto havepy
for /f "delims=" %%P in ('py -3 -c "import sys;print(sys.executable)" 2^>nul') do if not defined PYEXE call :trypy "%%P"
if defined PYEXE goto havepy
echo.
echo [rules] ERROR: Python not found.
echo         Double-click the setup entry (file starting with 0) first,
echo         or install Python 3.8+ from python.org
if "%GETLEC_NOPAUSE%"=="" pause
exit /b 9009

:havepy
"%PYEXE%" "%~dp0tools\rules.py" %*
set "RC=%ERRORLEVEL%"
if "%GETLEC_NOPAUSE%"=="" pause
exit /b %RC%

:trypy
"%~1" -c "import sys" >nul 2>nul
if not errorlevel 1 set "PYEXE=%~1"
exit /b 0
