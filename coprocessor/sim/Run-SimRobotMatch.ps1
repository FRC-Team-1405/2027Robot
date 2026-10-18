<#
.SYNOPSIS
    Plays a scripted match in the laptop's robot SIMULATION while a real Orange Pi records it, then
    assembles a LogBench bundle (simulation .wpilog + the Pi's recordings) ready to open.

.DESCRIPTION
    Tier 2 of docs/logbench-e2e-test-plan.md. Unlike Run-SimulatedMatch.ps1 (a fake roboRIO that
    runs on the Pi, no AdvantageKit log), this runs the real robot code in `gradlew simulateJava`
    on this laptop. frc.robot.sim.ScriptedMatch drives the simulated Driver Station through
    disabled -> auto -> pause -> teleop -> disabled with random stick input, and the Pi's
    recorder connects to the simulation's NetworkTables server. The AdvantageKit log and the
    recordings therefore share one NT clock and one wall clock, exactly as on a real robot.

    Steps:
      1. On the Pi, a TEMPORARY systemd drop-in points orangepi-vision-recorder@<Camera> at this
         laptop (NT_SERVER) and names its recordings <LogCamera> so LogBench matches the log's
         camera. Recordings go to a throwaway ~/sim-recordings unless -UseRealRecordings.
      2. gradlew simulateJava runs headless (SIM_HEADLESS) and exits after the script, writing
         akit_<UTC time>_simmatch.wpilog into the output folder.
      3. The Pi's sessions are copied to <log>.vision\<LogCamera>\ beside the log, the service is
         restored (always, even on error), and testkit\check_bundle.py reports what was recorded.

    Run from YOUR OWN PowerShell, not an automated sandbox: Gradle needs normal network sockets.
    Prerequisites: Bootstrap-OrangePi.ps1 has been run (services installed); the Pi can reach this
    laptop on -LaptopAddress and Windows Firewall allows inbound TCP 5810 for Java (the first
    simulateJava run normally prompts; or, as admin:
      New-NetFirewallRule -DisplayName 'NT4 sim' -Direction Inbound -Protocol TCP -LocalPort 5810 -Action Allow ).

.PARAMETER Address        The Pi's address (for example 192.168.137.241 on the laptop's shared connection).
.PARAMETER LaptopAddress  This laptop's address as the Pi sees it (default 192.168.137.1, Windows' shared-connection address).
.PARAMETER Camera         The Pi's recorder instance name (default bench).
.PARAMETER LogCamera      The camera name to record as, matching the robot's camera (default LeftCam).
.PARAMETER Script         ScriptedMatch script: 'default' or 'disabled:10,auto:20,disabled:3,teleop:140,disabled:10'.
.PARAMETER Fast           Divide every phase duration by this.
.PARAMETER UseRealRecordings  Record into the Pi's normal ~/vision-recordings (mixes with real data) instead of a throwaway folder.

.EXAMPLE
    .\Run-SimRobotMatch.ps1 -Address 192.168.137.241 -KeyPath $HOME\.ssh\id_ed25519_claude -Fast 4
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Address,
    [string]$User = 'pi',
    [string]$KeyPath = (Join-Path $HOME '.ssh\id_ed25519_orangepi'),
    [string]$LaptopAddress = '192.168.137.1',
    [string]$Camera = 'bench',
    [string]$LogCamera = 'LeftCam',
    [string]$Script = 'default',
    [double]$Fast = 1,
    [int]$NtPort = 5810,
    [double]$SampleHz = 3,
    [int]$WaitClients = 1,
    [string]$OutDir = '',
    [switch]$UseRealRecordings,
    [switch]$NoCheck
)
$ErrorActionPreference = 'Stop'
$simDir = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $simDir '..\..')).Path
if (-not $OutDir) { $OutDir = Join-Path $simDir ("runs\{0}-simrobot" -f (Get-Date -Format 'yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$sshBase = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ServerAliveInterval=15', '-i', $KeyPath, '-o', 'IdentitiesOnly=yes')

function Say($m, $c = 'White') { Write-Host $m -ForegroundColor $c }

function Invoke-Native([string]$File, [string[]]$Arguments, [int]$TimeoutSec = 120) {
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    $psi.Arguments = ($Arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    $psi.UseShellExecute = $false; $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true
    $p = New-Object System.Diagnostics.Process; $p.StartInfo = $psi; [void]$p.Start()
    $o = $p.StandardOutput.ReadToEndAsync(); $e = $p.StandardError.ReadToEndAsync()
    if (-not $p.WaitForExit($TimeoutSec * 1000)) { try { $p.Kill() } catch {}; return [pscustomobject]@{ ExitCode = 124; Out = ''; Err = 'timeout' } }
    return [pscustomobject]@{ ExitCode = $p.ExitCode; Out = $o.Result; Err = $e.Result }
}
function Invoke-Pi([string]$Cmd, [int]$TimeoutSec = 120) { Invoke-Native 'ssh' ($sshBase + @("$User@$Address", $Cmd)) $TimeoutSec }
function Require-Ok($r, [string]$What) {
    if ($r.ExitCode -ne 0) { throw ("{0} failed (exit {1}): {2}" -f $What, $r.ExitCode, (($r.Err -split "`n" | Select-Object -Last 3) -join ' ')) }
}

$unit = "orangepi-vision-recorder@$Camera.service"
$dropDir = "/etc/systemd/system/orangepi-vision-recorder@$Camera.service.d"
$envFile = "/etc/orangepi-vision-recorder/sim-$Camera.env"
$recDir = if ($UseRealRecordings) { '/home/pi/vision-recordings' } else { '/home/pi/sim-recordings' }
$dropInstalled = $false

Say "== Simulated robot match, recorded by $User@$Address as camera '$LogCamera' ==" Cyan
Say "   results -> $OutDir" DarkGray

$r = Invoke-Pi "systemctl cat $unit >/dev/null && sudo -n true && echo READY"
if ($r.Out -notmatch 'READY') { throw "Pi not ready (need the recorder service and passwordless sudo). Run Bootstrap-OrangePi.ps1 first. $($r.Err)" }
$ping = Invoke-Pi "timeout 3 bash -c '</dev/tcp/$LaptopAddress/22' 2>&1; ping -c1 -W2 $LaptopAddress >/dev/null 2>&1 && echo PONG"
if ($ping.Out -notmatch 'PONG') { Say "   warning: the Pi could not ping $LaptopAddress - check -LaptopAddress and the shared connection" Yellow }

$gradleProc = $null
try {
    Say "1) Pointing $unit at this laptop's simulation ($LaptopAddress`:$NtPort), recording as '$LogCamera'" White
    $lines = "NT_SERVER=$LaptopAddress\nNT_PORT=$NtPort\nCAMERA_NAME=$LogCamera\nSAMPLE_HZ=$SampleHz\n"
    if (-not $UseRealRecordings) { $lines += "RECORDINGS_DIR=$recDir\n" }
    $setup = "set -e; sudo rm -rf $recDir/$LogCamera; mkdir -p $recDir; " +
        "printf '$lines' | sudo tee $envFile >/dev/null; " +
        "sudo mkdir -p $dropDir; printf '[Service]\nEnvironmentFile=$envFile\n' | sudo tee $dropDir/sim.conf >/dev/null; " +
        "sudo systemctl daemon-reload; sudo systemctl restart $unit; sleep 2; systemctl is-active $unit"
    $r = Invoke-Pi $setup
    if ($r.Out -notmatch 'active') { throw "recorder did not start: $($r.Err)" }
    $dropInstalled = $true

    Say '2) Starting the headless simulation (Gradle; the first run can take a few minutes)' White
    $env:SIM_HEADLESS = '1'
    $env:SIM_MATCH_SCRIPT = $Script
    $env:SIM_MATCH_FAST = "$Fast"
    $env:SIM_MATCH_WAIT_CLIENTS = "$WaitClients"
    $env:SIM_MATCH_EXIT = '1'
    $env:SIM_LOG_DIR = $OutDir
    $simOut = Join-Path $OutDir 'simulate.log'
    $gradle = Join-Path $repo 'gradlew.bat'
    $gradleProc = Start-Process -FilePath $gradle -ArgumentList @('simulateJava', '--console=plain') -WorkingDirectory $repo `
        -RedirectStandardOutput $simOut -RedirectStandardError (Join-Path $OutDir 'simulate.err.log') -PassThru -WindowStyle Hidden

    $seen = 0; $t0 = Get-Date; $limit = 900
    while (-not $gradleProc.HasExited) {
        Start-Sleep -Seconds 3
        if (Test-Path $simOut) {
            $marks = @(Get-Content $simOut | Where-Object { $_ -match '^SIMMATCH' })
            for ($i = $seen; $i -lt $marks.Count; $i++) { Say ('   ' + $marks[$i]) DarkGray }
            $seen = $marks.Count
        }
        if (((Get-Date) - $t0).TotalSeconds -gt $limit) { throw "simulation still running after $limit s; see $simOut" }
    }
    if ($gradleProc.ExitCode -ne 0) { throw "simulateJava exited with $($gradleProc.ExitCode); see $simOut and simulate.err.log" }
    $log = Get-ChildItem $OutDir -Filter 'akit_*_simmatch.wpilog' | Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $log) { throw "no akit_*_simmatch.wpilog in $OutDir; did the simulation start Logger with SIM_LOG_DIR?" }
    if (-not (Get-Content $simOut | Where-Object { $_ -match '^SIMMATCH start' })) {
        throw "the script never started - no NT client connected ($WaitClients wanted). Is inbound TCP $NtPort allowed through Windows Firewall?"
    }
    Start-Sleep -Seconds 3   # let the recorder close its last session

    Say '3) Collecting the Pi recordings into the bundle' White
    $visionDir = Join-Path $OutDir ($log.BaseName + '.vision')
    New-Item -ItemType Directory -Force $visionDir | Out-Null
    $null = Invoke-Pi "sudo chown -R pi:pi $recDir/$LogCamera 2>/dev/null; echo ok"
    $x = Invoke-Native 'scp' ($sshBase + @('-q', '-r', "$User@${Address}:$recDir/$LogCamera", $visionDir)) 600
    Require-Ok $x 'fetch recordings'
}
finally {
    Say '4) Restoring the recorder service to its normal configuration' White
    if ($dropInstalled) {
        try {
            $null = Invoke-Pi "sudo rm -rf $dropDir $envFile; sudo systemctl daemon-reload; sudo systemctl restart $unit; sleep 1; systemctl is-active $unit"
            Say ('   service state: ' + ((Invoke-Pi "systemctl is-active $unit").Out.Trim())) Green
        } catch { Say "   RESTORE FAILED - run on the Pi:  sudo rm -rf $dropDir $envFile ; sudo systemctl daemon-reload ; sudo systemctl restart $unit" Red }
    }
    if ($gradleProc -and -not $gradleProc.HasExited) { try { Stop-Process -Id $gradleProc.Id -Force } catch {} }
    foreach ($n in 'SIM_HEADLESS', 'SIM_MATCH_SCRIPT', 'SIM_MATCH_FAST', 'SIM_MATCH_WAIT_CLIENTS', 'SIM_MATCH_EXIT', 'SIM_LOG_DIR') {
        Remove-Item "Env:$n" -ErrorAction SilentlyContinue
    }
}

Say ''
Say 'Bundle ready:' Green
Say "   $OutDir"
Say "Open it in LogBench:   python tools\logbench\server\main.py --logs `"$OutDir`"" White
if (-not $NoCheck) {
    Say '5) Checking the bundle' White
    $py = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { 'py' }
    & $py (Join-Path $repo 'tools\logbench\testkit\check_bundle.py') $OutDir --expect-cameras $LogCamera
    exit $LASTEXITCODE
}
