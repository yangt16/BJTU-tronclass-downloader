@echo off
REM ===========================================================
REM  Start downloading. Double-click this file.
REM
REM  No arguments: shows the interactive menu
REM      product : video + audio / audio only / video only
REM      scope   : all / one day / weekdays / exclude weekdays
REM
REM  Drop a list file onto this icon: runs that list directly,
REM  default settings (video + audio, everything), no menu.
REM
REM  HARD RULES: ASCII only, no angle brackets in comments, CRLF.
REM ===========================================================
setlocal
chcp 65001 >nul
cd /d "%~dp0"

if not "%~1"=="" (
    call "%~dp0tools\getlec.cmd" %*
    exit /b %ERRORLEVEL%
)
call "%~dp0tools\getlec.cmd" --menu
exit /b %ERRORLEVEL%
