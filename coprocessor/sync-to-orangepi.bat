@echo off
setlocal
rem Version: 2026-10-03.3
 echo sync-to-orangepi version 2026-10-03.3

rem Copies the coprocessor folder with SCP to /home/pi/coprocessor.
rem Usage: sync-to-orangepi.bat [pi@host] [--setup]
rem Example: sync-to-orangepi.bat pi@192.168.1.252 --setup

set "DEFAULT_TARGET=pi@photonvision.local"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%DEFAULT_TARGET%"
set "MODE=%~2"

if not "%~3"=="" goto usage
if not "%MODE%"=="" if /I not "%MODE%"=="--setup" goto usage
if not "%TARGET:~0,3%"=="pi@" (
    echo ERROR: The correct SSH user is pi. Use pi@hostname or pi@ip-address.
    exit /b 2
)

where ssh >nul 2>&1
if errorlevel 1 (
    echo ERROR: OpenSSH client ^(ssh^) was not found.
    echo Install the Windows OpenSSH Client optional feature, then run this script again.
    exit /b 1
)

where scp >nul 2>&1
if errorlevel 1 (
    echo ERROR: OpenSSH file-copy client ^(scp^) was not found.
    echo Install the Windows OpenSSH Client optional feature, then run this script again.
    exit /b 1
)

echo Checking connection to %TARGET%...
ssh -o ConnectTimeout=5 "%TARGET%" "test -d /home/pi && test -w /home/pi"
if errorlevel 1 (
    echo ERROR: Could not connect to %TARGET% or /home/pi is not writable by pi.
    echo Verify the Orange Pi is powered, connected to the robot network, and that the SSH user/host is correct.
    echo You can specify a different target, for example:
    echo   %~nx0 pi@192.168.1.252
    exit /b 1
)

rem Use a relative source from the repo root to avoid drive-letter/colon ambiguity
rem in SCP paths. pushd also handles repo paths containing spaces or UNC shares.
pushd "%~dp0.."
if errorlevel 1 (
    echo ERROR: Could not open the parent of the coprocessor folder.
    exit /b 1
)
if not exist "coprocessor\setup-orangepi.sh" (
    popd
    echo ERROR: Keep this batch file in the repository's coprocessor folder.
    exit /b 1
)

echo Copying coprocessor folder to %TARGET%:/home/pi/coprocessor...
scp -r -p -o ConnectTimeout=5 "coprocessor" "%TARGET%:/home/pi/"
set "COPY_RESULT=%ERRORLEVEL%"
popd
if not "%COPY_RESULT%"=="0" (
    echo ERROR: SCP transfer failed. Review the error above; check connection, permissions, and free space.
    echo Services have not been installed or restarted by this batch file.
    exit /b 1
)

echo Copy complete. Files with matching names have been overwritten; extra remote files are retained.
rem Windows checkouts can contain CRLF; normalize all copied Bash scripts.
ssh -o ConnectTimeout=5 "%TARGET%" "sed -i 's/\r$//' /home/pi/coprocessor/*.sh"
if errorlevel 1 (
    echo ERROR: Files copied, but preparing the Bash installer failed. Services were not restarted.
    exit /b 1
)
echo Checking copied fan installer version...
ssh -o ConnectTimeout=5 "%TARGET%" "bash /home/pi/coprocessor/enable-fan.sh --version"
if errorlevel 1 (
    echo ERROR: Could not verify the copied fan installer. Review the output above.
    exit /b 1
)
if /I "%MODE%"=="--setup" (
    echo Running the service installer on the Pi...
    ssh -t -o ConnectTimeout=5 "%TARGET%" "cd /home/pi/coprocessor && bash setup-orangepi.sh"
    if errorlevel 1 (
        echo ERROR: Files copied, but the service installer failed. Review its diagnostics above.
        exit /b 1
    )
) else (
    echo To install/update services, SSH into the Pi and run:
    echo   cd /home/pi/coprocessor
    echo   bash setup-orangepi.sh
    echo Or rerun this batch file with: %~nx0 %TARGET% --setup
)

endlocal
exit /b 0

:usage
echo Usage: %~nx0 [pi@host] [--setup]
echo Example: %~nx0 pi@192.168.1.252 --setup
exit /b 2
