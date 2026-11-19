@echo off
REM ===========================================================
REM  Download only selected day(s) or weekday(s).
REM
REM  Asks for a date or a weekday number, then runs the normal
REM  batch with a filter. Works on every list in lists\ at once:
REM  days a course does not have are simply ignored.
REM
REM  What you can type:
REM     20261030              one day
REM     20261030,20261104     several days
REM     4                     every Thursday (1=Mon .. 7=Sun)
REM     2,4                   Monday and Thursday
REM     (empty)               no filter, download everything
REM
REM  The list is NOT archived when filtering, so it stays usable.
REM
REM  HARD RULES: ASCII only, no angle brackets in comments, CRLF.
REM ===========================================================
setlocal
chcp 65001 >nul

echo ============================================================
echo  Download only selected day(s) / weekday(s)
echo ============================================================
set "DAY="
set /p "DAY=Date 20261030 or weekday 1-7 (1=Mon..7=Sun), comma ok, empty=all: "

if not defined DAY goto runall

REM validate: digits and commas only
echo %DAY%| findstr /r "^[0-9][0-9,]*$" >nul
if errorlevel 1 goto bad

set "GETLEC_ONLY=%DAY%"
goto run

:bad
echo.
echo [day] ERROR: bad input: "%DAY%"
echo       Use 8-digit date (20261030) or weekday 1-7 (1=Mon..7=Sun), comma for several
echo.
if "%GETLEC_NOPAUSE%"=="" pause
exit /b 1

:runall
echo.
echo [day] no filter, downloading everything

:run
echo.
call "%~dp0tools\getlec.cmd" %*
exit /b %ERRORLEVEL%
