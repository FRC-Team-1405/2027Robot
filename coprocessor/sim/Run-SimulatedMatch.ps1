<#
.SYNOPSIS
    Plays a full simulated match on an Orange Pi with NO roboRIO and verifies the vision recordings.

.DESCRIPTION
    Runs from the laptop (PowerShell). On the Pi it temporarily points the real
    orangepi-vision-recorder@<camera>.service at a fake roboRIO (fake_robot.py, listening on the
    Pi itself), plays pre-match -> auto -> pause -> teleop -> post-match, records the real
    PhotonVision stream the whole time, then restores the service and pulls the results back and
    runs verify_recordings.py on them.

    Ground truth comes from two extra helpers on the Pi:
      fake_robot.py  logs exactly when each phase started (event log)
      frame_tap.py   logs when every frame left PhotonVision, so each recorded frame's true age can be computed

    The recorder service is ALWAYS restored to its normal configuration at the end (even on error),
    and recordings go to a throwaway ~/sim-recordings, never your real ~/vision-recordings.
    Prerequisites: run Bootstrap-OrangePi.ps1 first (installs the services and copies sim\*.py to the Pi).

.PARAMETER Fast
    Divide all phase durations by this (default 1 = real match: 20 s auto, 3 s pause, 140 s teleop).

.PARAMETER Extra
    Extra fake_robot.py arguments, e.g. '--drop-at-sec 30 --drop-for-sec 3' or '--no-clock'.

.EXAMPLE
    .\Run-SimulatedMatch.ps1 -Address 192.168.137.241 -KeyPath $HOME\.ssh\id_ed25519_claude
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$Address,
    [string]$User = 'pi',
    [string]$KeyPath = (Join-Path $HOME '.ssh\id_ed25519_orangepi'),
    [string]$Camera = 'bench',
    [double]$Fast = 1,
    [string]$Extra = '',
    [int]$Port = 5811,
    [string]$StreamUrl = '',
    [double]$SampleHz = 3,
    [string]$OutDir = '',
    [string]$Label = 'run',
    [switch]$NoVerify
)
$ErrorActionPreference = 'Stop'
$simDir = $PSScriptRoot
if (-not $OutDir) { $OutDir = Join-Path $simDir ("runs\{0}-{1}" -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $Label) }
New-Item -ItemType Directory -Force $OutDir | Out-Null
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
function Invoke-Pi([string]$Cmd, [int]$TimeoutSec = 120) {
    $r = Invoke-Native 'ssh' ($sshBase + @("$User@$Address", $Cmd)) $TimeoutSec
    return $r
}
function Require-Ok($r, [string]$What) {
    if ($r.ExitCode -ne 0) { throw ("{0} failed (exit {1}): {2}" -f $What, $r.ExitCode, (($r.Err -split "`n" | Select-Object -Last 3) -join ' ')) }
}

$unit = "orangepi-vision-recorder@$Camera.service"
$dropDir = "/etc/systemd/system/orangepi-vision-recorder@$Camera.service.d"
$venvPy = '/home/pi/.venv-ntpublisher/bin/python3'
$simPi = '/home/pi/coprocessor/sim'
$restored = $false

Say "== Simulated match on $User@$Address, camera '$Camera', speed x$Fast ==" Cyan
Say "   results -> $OutDir" DarkGray

# --- preflight
$r = Invoke-Pi "test -f $simPi/fake_robot.py && test -f $simPi/frame_tap.py && systemctl cat $unit >/dev/null && sudo -n true && echo READY"
if ($r.Out -notmatch 'READY') { throw "Pi not ready (need sim scripts, the recorder service, passwordless sudo). Run Bootstrap-OrangePi.ps1 first. $($r.Err)" }
$envLines = (Invoke-Pi "sudo cat /etc/orangepi-vision-recorder/$Camera.env").Out
if (-not $StreamUrl) { $m = [regex]::Match($envLines, 'CAMERA_STREAM_URL=(\S+)'); $StreamUrl = $m.Groups[1].Value }
if (-not $StreamUrl) { throw "No CAMERA_STREAM_URL found in /etc/orangepi-vision-recorder/$Camera.env" }
Say "   stream: $StreamUrl" DarkGray

try {
    # --- point the real service at the fake robot (drop-in; undone in finally)
    Say "1) Pointing $unit at a fake roboRIO on the Pi (temporary systemd drop-in)" White
    $envFile = "/etc/orangepi-vision-recorder/sim-$Camera.env"
    $setup = "set -e; sudo rm -rf /home/pi/sim-recordings /tmp/sim; mkdir -p /tmp/sim /home/pi/sim-recordings; " +
        "printf 'NT_SERVER=127.0.0.1\nNT_PORT=$Port\nRECORDINGS_DIR=/home/pi/sim-recordings\nSAMPLE_HZ=$SampleHz\n' | sudo tee $envFile >/dev/null; " +
        "sudo mkdir -p $dropDir; printf '[Service]\nEnvironmentFile=$envFile\n' | sudo tee $dropDir/sim.conf >/dev/null; " +
        "sudo systemctl daemon-reload; sudo systemctl restart $unit; sleep 2; systemctl is-active $unit"
    $r = Invoke-Pi $setup
    if ($r.Out -notmatch 'active') { throw "recorder did not start: $($r.Err)" }
    $since = (Invoke-Pi 'date +"%Y-%m-%d %H:%M:%S"').Out.Trim()

    # --- start the ground-truth tap and the fake robot (background, so ssh dropouts cannot kill the run)
    Say '2) Starting frame tap + fake roboRIO' White
    $start = "cd $simPi; nohup $venvPy frame_tap.py --url $StreamUrl --out /tmp/sim/tap.jsonl > /tmp/sim/tap.log 2>&1 & echo `$! > /tmp/sim/tap.pid; " +
        "nohup $venvPy fake_robot.py --listen 127.0.0.1 --port $Port --wait-for-clients 1 --fast $Fast --event-log /tmp/sim/events.jsonl $Extra > /tmp/sim/robot.log 2>&1 & echo started"
    $r = Invoke-Pi $start
    Require-Ok $r 'start'
    # --- wait for 'done'
    $est = [math]::Ceiling((5 + 20 + 3 + 140 + 10) / $Fast) + 30
    Say ("3) Match running (about {0} s). Phases as they happen:" -f $est) White
    $seen = 0; $t0 = Get-Date; $done = $false
    while (((Get-Date) - $t0).TotalSeconds -lt ($est + 120)) {
        Start-Sleep -Seconds 5
        $r = Invoke-Pi 'cat /tmp/sim/robot.log 2>/dev/null'
        $lines = @($r.Out -split "`r?`n" | Where-Object { $_ -match '^\[' })
        for ($i = $seen; $i -lt $lines.Count; $i++) { Say ("   " + $lines[$i]) DarkGray }
        $seen = $lines.Count
        if ($r.Out -match '\]\s+done\s') { $done = $true; break }
        if ($r.Out -match 'Traceback') { throw "fake_robot crashed: $($r.Out)" }
    }
    if (-not $done) { throw 'Timed out waiting for the fake match to finish.' }
    Start-Sleep -Seconds 3
    $null = Invoke-Pi 'kill $(cat /tmp/sim/tap.pid) 2>/dev/null; sleep 1; echo ok'

    # --- collect
    Say '4) Collecting results' White
    $null = Invoke-Pi "sudo journalctl -u $unit --since '$since' --no-pager -o short-iso > /tmp/sim/recorder.log 2>&1; sudo chown -R pi:pi /home/pi/sim-recordings; echo ok"
    foreach ($f in 'events.jsonl', 'tap.jsonl', 'recorder.log', 'robot.log', 'tap.log') {
        $x = Invoke-Native 'scp' ($sshBase + @('-q', "$User@${Address}:/tmp/sim/$f", (Join-Path $OutDir $f))) 300
        if ($x.ExitCode -ne 0) { Say "   (could not fetch $f)" Yellow }
    }
    $x = Invoke-Native 'scp' ($sshBase + @('-q', '-r', "$User@${Address}:/home/pi/sim-recordings/$Camera", (Join-Path $OutDir 'recordings'))) 600
    Require-Ok $x 'fetch recordings'
}
finally {
    Say '5) Restoring the recorder service to its normal configuration' White
    try {
        $null = Invoke-Pi "sudo rm -rf $dropDir $envFile; sudo systemctl daemon-reload; sudo systemctl restart $unit; sleep 1; systemctl is-active $unit"
        $r = Invoke-Pi "systemctl is-active $unit; systemctl cat $unit | grep -c sim"
        Say ("   service state: " + (($r.Out -split "`n")[0])) Green
    } catch { Say "   RESTORE FAILED - run:  sudo rm -rf $dropDir ; sudo systemctl daemon-reload ; sudo systemctl restart $unit" Red }
}

if (-not $NoVerify) {
    Say '6) Verifying the recordings' White
    $py = if (Get-Command python -ErrorAction SilentlyContinue) { 'python' } else { 'py' }
    $camDir = Join-Path $OutDir 'recordings'
    $out = & $py (Join-Path $simDir 'verify_recordings.py') --events (Join-Path $OutDir 'events.jsonl') --recordings $camDir --tap (Join-Path $OutDir 'tap.jsonl') --sample-hz $SampleHz --json-out (Join-Path $OutDir 'verify.json') 2>&1
    $code = $LASTEXITCODE
    $out | Set-Content -Path (Join-Path $OutDir 'verify.txt') -Encoding UTF8
    $out | ForEach-Object { Write-Host $_ }
    exit $code
}
