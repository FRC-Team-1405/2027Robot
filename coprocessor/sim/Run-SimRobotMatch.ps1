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

    Several cameras are recorded at once (-LogCameras, default LeftCam,RightCam) so the dashboard's
    camera switching can be exercised. The Pi has one webcam, so the FIRST camera records the real
    PhotonVision stream and every other camera records a fake camera (fake_mjpeg.py running on the
    Pi, a frame counter and clock) -- visually obvious which feed you are looking at.

    Steps:
      1. On the Pi, one TEMPORARY recorder instance per camera is started
         (orangepi-vision-recorder@<LogCamera>, with a temporary env file pointing it at this laptop's
         NT server). The Pi's normal @<Camera> service is not touched. Recordings go to a throwaway
         ~/sim-recordings unless -UseRealRecordings.
      2. gradlew simulateJava runs headless (SIM_HEADLESS) and exits after the script, writing
         akit_<UTC time>_simmatch.wpilog into the output folder.
      3. The Pi's sessions are copied to <log>.vision\<LogCamera>\ beside the log, the temporary
         instances and fake cameras are removed (always, even on error), and testkit\check_bundle.py
         reports what was recorded.

    Run from YOUR OWN PowerShell, not an automated sandbox: Gradle needs normal network sockets.
    Prerequisites: Bootstrap-OrangePi.ps1 has been run (services installed); the Pi can reach this
    laptop on -LaptopAddress and Windows Firewall allows inbound TCP 5810 for Java (the first
    simulateJava run normally prompts; or, as admin:
      New-NetFirewallRule -DisplayName 'NT4 sim' -Direction Inbound -Protocol TCP -LocalPort 5810 -Action Allow ).

.PARAMETER Address        The Pi's address (for example 192.168.137.241 on the laptop's shared connection).
.PARAMETER LaptopAddress  This laptop's address as the Pi sees it (default 192.168.137.1, Windows' shared-connection address).
.PARAMETER Camera         The Pi's normal recorder instance (default bench); only read, to learn the real stream URL.
.PARAMETER LogCameras     Camera names to record as, matching the robot's cameras (default LeftCam,RightCam). The first is the real camera.
.PARAMETER Script         ScriptedMatch script: 'default' or 'disabled:10,auto:20,disabled:3,teleop:140,disabled:10'.
.PARAMETER Fast           Divide every phase duration by this.
.PARAMETER CollectOnly    Do not run anything: only copy the Pi's recordings from an earlier run into -OutDir (which must
                      already hold that run's .wpilog) and check the bundle. Use it when a run stopped before the copy step;
                      the Pi keeps the recordings until the next run starts.
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
    [string]$LogCameras = 'LeftCam,RightCam',
    [string]$Script = 'default',
    [double]$Fast = 1,
    [int]$NtPort = 5810,
    [double]$SampleHz = 3,
    [int]$WaitClients = 0,
    [int]$FakeCameraPort = 1191,
    [string]$OutDir = '',
    [switch]$UseRealRecordings,
    [switch]$CollectOnly,
    [switch]$NoCheck
)
$ErrorActionPreference = 'Stop'
$simDir = $PSScriptRoot
$repo = (Resolve-Path (Join-Path $simDir '..\..')).Path
if (-not $OutDir) { $OutDir = Join-Path $simDir ("runs\{0}-simrobot" -f (Get-Date -Format 'yyyyMMdd-HHmmss')) }
New-Item -ItemType Directory -Force $OutDir | Out-Null
$OutDir = (Resolve-Path $OutDir).Path
$cams = @($LogCameras -split ',' | ForEach-Object { $_.Trim() } | Where-Object { $_ })
if ($cams.Count -lt 1) { throw 'Give at least one camera in -LogCameras.' }
if ($WaitClients -le 0) { $WaitClients = $cams.Count }
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

$recDir = if ($UseRealRecordings) { '/home/pi/vision-recordings' } else { '/home/pi/sim-recordings' }
$venvPy = '/home/pi/.venv-ntpublisher/bin/python3'
$simPi = '/home/pi/coprocessor/sim'
$setupDone = $false

Say "== Simulated robot match, recorded by $User@$Address as cameras: $($cams -join ', ') ==" Cyan
Say "   results -> $OutDir" DarkGray

$r = Invoke-Pi "systemctl cat orangepi-vision-recorder@.service >/dev/null && test -f $simPi/fake_mjpeg.py && sudo -n true && echo READY"
if ($r.Out -notmatch 'READY') { throw "Pi not ready (need the recorder service template, the sim scripts and passwordless sudo). Run Bootstrap-OrangePi.ps1 first. $($r.Err)" }
$benchEnv = (Invoke-Pi "sudo cat /etc/orangepi-vision-recorder/$Camera.env").Out
$realStream = [regex]::Match($benchEnv, 'CAMERA_STREAM_URL=(\S+)').Groups[1].Value
if (-not $realStream) { throw "No CAMERA_STREAM_URL in /etc/orangepi-vision-recorder/$Camera.env" }
$streams = @{}
for ($i = 0; $i -lt $cams.Count; $i++) {
    $streams[$cams[$i]] = if ($i -eq 0) { $realStream } else { "http://127.0.0.1:$($FakeCameraPort + $i - 1)/stream.mjpg" }
    $kind = if ($i -eq 0) { '(real camera)' } else { '(fake camera)' }
    Say ("   {0}: {1}  {2}" -f $cams[$i], $streams[$cams[$i]], $kind) DarkGray
}
$ping = Invoke-Pi "timeout 3 bash -c '</dev/tcp/$LaptopAddress/22' 2>&1; ping -c1 -W2 $LaptopAddress >/dev/null 2>&1 && echo PONG"
if ($ping.Out -notmatch 'PONG') { Say "   warning: the Pi could not ping $LaptopAddress - check -LaptopAddress and the shared connection" Yellow }

$gradleProc = $null
$simOut = Join-Path $OutDir 'simulate.log'
$simError = $null
try {
  if (-not $CollectOnly) {
    Say "1) Starting a temporary recorder per camera, pointed at this laptop's simulation ($LaptopAddress`:$NtPort)" White
    $setup = "set -e; mkdir -p /tmp/simrobot $recDir; "
    for ($i = 0; $i -lt $cams.Count; $i++) {
        $c = $cams[$i]
        $setup += "sudo rm -rf $recDir/$c; "
        if ($i -gt 0) {
            $port = $FakeCameraPort + $i - 1
            $setup += "nohup $venvPy $simPi/fake_mjpeg.py --port $port --fps 30 > /tmp/simrobot/fake-$c.log 2>&1 & echo `$! > /tmp/simrobot/fake-$c.pid; "
        }
        $lines = "CAMERA_STREAM_URL=$($streams[$c])\nNT_SERVER=$LaptopAddress\nNT_PORT=$NtPort\nSAMPLE_HZ=$SampleHz\n"
        if (-not $UseRealRecordings) { $lines += "RECORDINGS_DIR=$recDir\n" }
        $setup += "printf '$lines' | sudo tee /etc/orangepi-vision-recorder/$c.env >/dev/null; "
    }
    $setup += "sleep 1; sudo systemctl daemon-reload; "
    foreach ($c in $cams) { $setup += "sudo systemctl restart orangepi-vision-recorder@$c.service; " }
    $units = ($cams | ForEach-Object { "orangepi-vision-recorder@$_" }) -join ' '
    $setup += "sleep 2; for u in $units; do systemctl is-active `$u; done"
    $r = Invoke-Pi $setup
    $setupDone = $true
    $active = @($r.Out -split "`r?`n" | Where-Object { $_ -eq 'active' }).Count
    if ($active -lt $cams.Count) { throw "recorders did not all start: $($r.Out) $($r.Err)" }

    Say '2) Starting the headless simulation (Gradle; the first run can take a few minutes)' White
    $env:SIM_HEADLESS = '1'
    $env:SIM_MATCH_SCRIPT = $Script
    $env:SIM_MATCH_FAST = "$Fast"
    $env:SIM_MATCH_WAIT_CLIENTS = "$WaitClients"
    $env:SIM_MATCH_EXIT = '1'
    $env:SIM_LOG_DIR = $OutDir
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
    # Start-Process -PassThru leaves ExitCode empty until WaitForExit() has been called on the object.
    $gradleProc.WaitForExit()
    $simCode = $gradleProc.ExitCode
    $simFinished = [bool](Get-Content $simOut | Where-Object { $_ -match '^SIMMATCH exit' })
    # Never throw here: the recordings on the Pi still have to be copied. Report it after they are.
    if (-not $simFinished -and $null -ne $simCode -and $simCode -ne 0) {
        $simError = "simulateJava exited with $simCode; see $simOut and simulate.err.log"
    }
  }
    $log = Get-ChildItem $OutDir -Filter 'akit_*_simmatch.wpilog' | Sort-Object LastWriteTime | Select-Object -Last 1
    if (-not $log) { throw "no akit_*_simmatch.wpilog in $OutDir; did the simulation start Logger with SIM_LOG_DIR?" }
    if (-not $CollectOnly -and -not (Get-Content $simOut | Where-Object { $_ -match '^SIMMATCH start' })) {
        throw "the script never started - no NT client connected ($WaitClients wanted). Is inbound TCP $NtPort allowed through Windows Firewall?"
    }
    Start-Sleep -Seconds 3   # let the recorder close its last session

    Say '3) Collecting the Pi recordings into the bundle' White
    $visionDir = Join-Path $OutDir ($log.BaseName + '.vision')
    New-Item -ItemType Directory -Force $visionDir | Out-Null
    foreach ($c in $cams) {
        $null = Invoke-Pi "sudo chown -R pi:pi $recDir/$c 2>/dev/null; echo ok"
        $x = Invoke-Native 'scp' ($sshBase + @('-q', '-r', "$User@${Address}:$recDir/$c", $visionDir)) 600
        Require-Ok $x "fetch $c recordings"
    }
    if ($simError) { throw $simError }
}
finally {
    if ($setupDone) {
        Say '4) Removing the temporary recorders and fake cameras' White
        try {
            $stop = "for c in $($cams -join ' '); do sudo systemctl stop orangepi-vision-recorder@`$c.service; sudo rm -f /etc/orangepi-vision-recorder/`$c.env; test -f /tmp/simrobot/fake-`$c.pid && kill `$(cat /tmp/simrobot/fake-`$c.pid) 2>/dev/null; done; sudo systemctl reset-failed 'orangepi-vision-recorder@*' 2>/dev/null; sudo systemctl daemon-reload; rm -rf /tmp/simrobot; echo cleaned"
            $r = Invoke-Pi $stop
            Say ('   ' + (@($r.Out -split "`r?`n" | Where-Object { $_ -eq 'cleaned' })[0])) Green
        } catch { Say "   CLEANUP FAILED - on the Pi: sudo systemctl stop 'orangepi-vision-recorder@*' (keep @$Camera running); remove the extra .env files in /etc/orangepi-vision-recorder; pkill -f fake_mjpeg.py" Red }
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
    & $py (Join-Path $repo 'tools\logbench\testkit\check_bundle.py') $OutDir --expect-cameras ($cams -join ',')
    exit $LASTEXITCODE
}
