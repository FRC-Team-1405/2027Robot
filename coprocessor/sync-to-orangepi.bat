@echo off
setlocal

rem Copies this folder's contents to the Orange Pi user's home directory.
rem Usage: sync-to-orangepi.bat [user@host]
rem Example: sync-to-orangepi.bat photon@192.168.1.252

set "DEFAULT_TARGET=photon@photonvision.local"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=%DEFAULT_TARGET%"

where ssh >nul 2>&1
if errorlevel 1 (
    echo ERROR: OpenSSH client ^(ssh^) was not found.
    echo Install the Windows OpenSSH Client optional feature, then run this script again.
    exit /b 1
)

where tar >nul 2>&1
if errorlevel 1 (
    echo ERROR: Windows tar was not found.
    echo Install a tar-compatible archiver or run this script from a current version of Windows.
    exit /b 1
)

echo Checking connection to %TARGET%...
ssh -o ConnectTimeout=5 "%TARGET%" "exit"
if errorlevel 1 (
    echo ERROR: Could not connect to %TARGET%.
    echo Verify the Orange Pi is powered, connected to the robot network, and that the SSH user/host is correct.
    echo You can specify a different target, for example:
    echo   %~nx0 photon@192.168.1.252
    exit /b 1
)

echo Syncing coprocessor files to %TARGET%:~...
rem --exclude keeps this deployment script from being copied to the Orange Pi.
tar -cf - --exclude="%~nx0" -C "%~dp0" . | ssh "%TARGET%" "tar -xf - -C ~"
if errorlevel 1 (
    echo ERROR: The file transfer to %TARGET% failed.
    exit /b 1
)

echo Sync complete.
endlocal
