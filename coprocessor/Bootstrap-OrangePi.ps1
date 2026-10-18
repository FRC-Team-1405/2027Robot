<#
.SYNOPSIS
    One-time LAPTOP-side setup for a new team Orange Pi (PowerShell, guided and interactive).

.DESCRIPTION
    Run this on the Windows laptop. It is NOT the same thing as setup-orangepi.sh, which runs
    ON the Pi; this script prepares the Pi and then drives setup-orangepi.sh for you.

    It follows docs/orangepi-internet-access.md and docs/orangepi-vision-recorder-setup.md and,
    for each step, tells you what it is about to do and why, then reports PASS / FAIL / ACTION.
    When something needs a human (enabling Internet Connection Sharing, activating the camera
    in PhotonVision, typing the Pi's password once), it stops and tells you exactly what to do.

    What it does:
      1  Preflight        OpenSSH client tools + repo files present
      2  Find the Pi      mDNS name, Internet-Connection-Sharing subnet, bench address, or -Address
      3  SSH key login    creates a key if needed, installs it on the Pi (you type the Pi password
                          into ssh itself; this script never sees it)
      4  Passwordless sudo (asks first)
      5  Pi health        OS, Python, disk, internet, clock
      6  Camera           USB camera seen, PhotonVision streams up, raw stream port confirmed
      7  PhotonVision     team number 1405 saved
      8  Plan             board NT name, camera instance(s), raw stream URL(s)
      9  Copy files       coprocessor scripts -> /home/pi/coprocessor
      10 Install          runs setup-orangepi.sh unattended (venv, pyntcore, services)
      11 Verify           services active, ntcore imports, recorder env correct

    It is safe to re-run: every step checks before it changes anything.

.PARAMETER Address
    The Pi's IP or hostname. If omitted the script searches for it.

.PARAMETER User
    SSH account on the Pi. Must be 'pi' (the installer requires it).

.PARAMETER KeyPath
    SSH private key to use (created if missing). Default: ~\.ssh\id_ed25519_orangepi

.PARAMETER BoardName
    Unique NetworkTables name for this board (e.g. LeftPi, RightPi). Prompted if omitted.

.PARAMETER Cameras
    Camera instance names hosted on THIS board, e.g. 'left' or 'front','rear'. Prompted if omitted.

.PARAMETER StreamUrls
    Hashtable of camera name -> RAW MJPEG URL as seen from the Pi, e.g. @{ left = 'http://localhost:1181/stream.mjpg' }.
    Prompted (with a probed default) if omitted.

.PARAMETER Yes
    Accept the safe default at every confirmation (it still stops for things only you can do).

.EXAMPLE
    .\Bootstrap-OrangePi.ps1

.EXAMPLE
    .\Bootstrap-OrangePi.ps1 -Address 192.168.137.241 -BoardName LeftPi -Cameras left
#>
[CmdletBinding()]
param(
    [string]$Address,
    [string]$User = 'pi',
    [string]$KeyPath = (Join-Path $HOME '.ssh\id_ed25519_orangepi'),
    [string]$BoardName,
    [string[]]$Cameras,
    [hashtable]$StreamUrls,
    [switch]$Yes
)

$ErrorActionPreference = 'Stop'
$script:Version = '2026-10-18.1'
$script:CoprocessorDir = $PSScriptRoot
$script:Results = New-Object System.Collections.ArrayList
$script:StepNumber = 0
$script:StepTotal = 11
$script:Pi = $null            # resolved address
$script:SshBase = @()         # common ssh args
$script:KnownIssue = @{}

# ---------------------------------------------------------------- output helpers (ASCII only)
function Write-Banner($text) { Write-Host ''; Write-Host ('=' * 78) -ForegroundColor DarkCyan; Write-Host $text -ForegroundColor Cyan; Write-Host ('=' * 78) -ForegroundColor DarkCyan }
function Write-Why($text)    { Write-Host ('  Why:  ' + $text) -ForegroundColor Gray }
function Write-Do($text)     { Write-Host ('  Doing: ' + $text) -ForegroundColor White }
function Write-Pass($text)   { Write-Host ('  [PASS] ' + $text) -ForegroundColor Green }
function Write-Warn2($text)  { Write-Host ('  [WARN] ' + $text) -ForegroundColor Yellow }
function Write-Fail($text)   { Write-Host ('  [FAIL] ' + $text) -ForegroundColor Red }
function Write-Action($text) { Write-Host ('  [YOU]  ' + $text) -ForegroundColor Magenta }
function Write-Info($text)   { Write-Host ('         ' + $text) -ForegroundColor DarkGray }

function Start-Step([string]$Title, [string]$Why) {
    $script:StepNumber++
    Write-Banner ("Step {0}/{1}: {2}" -f $script:StepNumber, $script:StepTotal, $Title)
    Write-Why $Why
}

function Add-Result([string]$Status, [string]$Title, [string]$Detail) {
    [void]$script:Results.Add([pscustomobject]@{ Step = $script:StepNumber; Status = $Status; Title = $Title; Detail = $Detail })
}

function Ask-YesNo([string]$Question, [bool]$Default = $true) {
    if ($Yes) { return $Default }
    $suffix = if ($Default) { '[Y/n]' } else { '[y/N]' }
    while ($true) {
        $a = (Read-Host ("  ? {0} {1}" -f $Question, $suffix)).Trim().ToLower()
        if ($a -eq '') { return $Default }
        if ($a -in @('y', 'yes')) { return $true }
        if ($a -in @('n', 'no')) { return $false }
    }
}

function Ask-Text([string]$Question, [string]$Default = '') {
    $shown = if ($Default) { " [$Default]" } else { '' }
    $a = (Read-Host ("  ? {0}{1}" -f $Question, $shown)).Trim()
    if ($a -eq '') { return $Default }
    return $a
}

function Wait-Enter([string]$Message) {
    if ($Yes) { return }
    [void](Read-Host ("  >> {0} Press Enter to continue" -f $Message))
}

# Thrown to stop the whole run with a clear message (after printing the summary).
class StepAbort : System.Exception { StepAbort([string]$m) : base($m) {} }
function Stop-Run([string]$Message) { throw [StepAbort]::new($Message) }

# ---------------------------------------------------------------- native process helper
# Runs an executable, returns stdout/stderr/exit code. Never throws on non-zero exit.
function Invoke-Native {
    param([string]$File, [string[]]$Arguments, [string]$StdIn, [int]$TimeoutSec = 120, [switch]$Inherit)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = $File
    # Quote args that contain spaces or quotes (Windows PowerShell 5.1 has no ArgumentList).
    $psi.Arguments = ($Arguments | ForEach-Object { if ($_ -match '[\s"]') { '"' + ($_ -replace '"', '\"') + '"' } else { $_ } }) -join ' '
    $psi.UseShellExecute = $false
    $psi.RedirectStandardInput = ($PSBoundParameters.ContainsKey('StdIn'))
    if (-not $Inherit) { $psi.RedirectStandardOutput = $true; $psi.RedirectStandardError = $true }
    $p = New-Object System.Diagnostics.Process
    $p.StartInfo = $psi
    [void]$p.Start()
    $outTask = $null; $errTask = $null
    if (-not $Inherit) { $outTask = $p.StandardOutput.ReadToEndAsync(); $errTask = $p.StandardError.ReadToEndAsync() }
    if ($psi.RedirectStandardInput) { $p.StandardInput.Write($StdIn); $p.StandardInput.Close() }
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        try { $p.Kill() } catch {}
        return [pscustomobject]@{ ExitCode = 124; Out = ''; Err = "timed out after $TimeoutSec s" }
    }
    $o = ''; $e = ''
    if (-not $Inherit) { $o = $outTask.Result; $e = $errTask.Result }
    return [pscustomobject]@{ ExitCode = $p.ExitCode; Out = $o; Err = $e }
}

# PhotonVision prints a big banner on every login (to stderr). Strip it so real errors stand out.
function Remove-PiBanner([string]$Text) {
    $keep = $Text -split "`r?`n" | Where-Object {
        $_ -notmatch '^\s*[#:\s]+\s*$' -and $_ -notmatch 'PhotonVision is the free|easy-to-use computer|for FIRST|To configure PhotonVision|using a computer on the same|network as this device|Documentation is available|docs\.photonvision|SSH Credentials|username is photon|password is vision|[#]{4}'
    }
    return ($keep -join "`n").Trim()
}

function Invoke-Pi {
    param([string]$Command, [int]$TimeoutSec = 120, [switch]$Tty)
    $a = @($script:SshBase)
    if ($Tty) { $a += '-t' }
    $a += @("$User@$script:Pi", $Command)
    $r = Invoke-Native -File 'ssh' -Arguments $a -TimeoutSec $TimeoutSec
    $r.Err = Remove-PiBanner $r.Err
    return $r
}

function Test-TcpPort([string]$HostName, [int]$Port, [int]$TimeoutMs = 1500) {
    $c = New-Object System.Net.Sockets.TcpClient
    try {
        $t = $c.ConnectAsync($HostName, $Port)
        return ($t.Wait($TimeoutMs) -and $c.Connected)
    } catch { return $false } finally { $c.Close() }
}

# Scan many addresses for an open port at once (fast, bounded).
function Find-OpenPort([string[]]$Hosts, [int]$Port, [int]$TimeoutMs = 2000) {
    $jobs = @()
    foreach ($h in $Hosts) {
        $c = New-Object System.Net.Sockets.TcpClient
        $jobs += [pscustomobject]@{ Host = $h; Client = $c; Task = $c.ConnectAsync($h, $Port) }
    }
    try { [void][System.Threading.Tasks.Task]::WaitAll(@($jobs | ForEach-Object { $_.Task }), $TimeoutMs) } catch {}
    $found = @($jobs | Where-Object { $_.Task.Status -eq 'RanToCompletion' -and $_.Client.Connected } | ForEach-Object { $_.Host })
    foreach ($j in $jobs) { $j.Client.Close() }
    return $found
}

# ---------------------------------------------------------------- steps
function Step-Preflight {
    Start-Step 'Preflight' 'Everything below uses the Windows OpenSSH client (ssh, scp, ssh-keygen) and the files in this folder.'
    $missing = @('ssh', 'scp', 'ssh-keygen') | Where-Object { -not (Get-Command $_ -ErrorAction SilentlyContinue) }
    if ($missing) {
        Write-Fail ("Missing: " + ($missing -join ', '))
        Write-Action 'Install the Windows optional feature "OpenSSH Client" (Settings > Apps > Optional features), then re-run.'
        Add-Result 'FAIL' 'Preflight' ("missing " + ($missing -join ', '))
        Stop-Run 'OpenSSH client not installed.'
    }
    Write-Pass 'ssh, scp and ssh-keygen are available.'
    $need = 'setup-orangepi.sh', 'orangepi-nt-publisher.py', 'orangepi-nt-publisher.service', 'orangepi-vision-recorder.py', 'orangepi-vision-recorder@.service'
    $absent = $need | Where-Object { -not (Test-Path (Join-Path $script:CoprocessorDir $_)) }
    if ($absent) {
        Write-Fail ("Not found next to this script: " + ($absent -join ', '))
        Write-Action 'Keep Bootstrap-OrangePi.ps1 inside the repo coprocessor folder.'
        Add-Result 'FAIL' 'Preflight' 'repo files missing'
        Stop-Run 'Coprocessor files not found.'
    }
    Write-Pass ("Coprocessor files found in {0}" -f $script:CoprocessorDir)
    if ($User -ne 'pi') { Write-Warn2 "setup-orangepi.sh requires the 'pi' account; -User '$User' will fail at the install step." }
    Add-Result 'PASS' 'Preflight' 'OpenSSH + repo files present'
}

function Step-FindPi {
    Start-Step 'Find the Pi' 'We need the Pi''s network address. A Pi plugged straight into the laptop''s USB-Ethernet dongle only gets one if Windows Internet Connection Sharing (ICS) is on.'
    if ($Address) {
        Write-Do "Checking the address you gave: $Address"
        if (Test-TcpPort $Address 22) { $script:Pi = $Address; Write-Pass "SSH answers at $Address"; Add-Result 'PASS' 'Find the Pi' $Address; return }
        Write-Fail "Nothing answers on port 22 at $Address."
        Add-Result 'FAIL' 'Find the Pi' "no SSH at $Address"
        Stop-Run "Pi not reachable at $Address. Check power, cable, and that the laptop and Pi share a network."
    }
    $attempt = 0
    while ($true) {
        $attempt++
        Write-Do 'Looking for a Pi (mDNS name, the ICS 192.168.137.x subnet, and the bench address)...'
        $candidates = New-Object System.Collections.ArrayList
        foreach ($n in 'photonvision.local', '192.168.1.252') { [void]$candidates.Add($n) }
        $ics = Get-NetIPAddress -AddressFamily IPv4 -ErrorAction SilentlyContinue | Where-Object { $_.IPAddress -like '192.168.137.*' }
        if ($ics) {
            Write-Info ("ICS adapter present: {0} ({1})" -f $ics[0].InterfaceAlias, $ics[0].IPAddress)
            2..254 | ForEach-Object { [void]$candidates.Add("192.168.137.$_") }
        } else {
            Write-Info 'No 192.168.137.x adapter on this laptop, so Internet Connection Sharing is probably off.'
        }
        $found = Find-OpenPort -Hosts @($candidates) -Port 22
        # Prefer ones that also answer PhotonVision's port.
        $pv = @($found | Where-Object { Test-TcpPort $_ 5800 800 })
        $pick = $null
        if ($pv.Count -ge 1) { $pick = $pv[0] } elseif ($found.Count -ge 1) { $pick = $found[0] }
        if ($pick -and (@($found).Count -gt 1 -or @($pv).Count -gt 1)) {
            Write-Warn2 ("More than one SSH host found: {0}" -f ($found -join ', '))
            $pick = Ask-Text 'Which one is the Orange Pi?' $pick
        }
        if ($pick) {
            $script:Pi = $pick
            Write-Pass ("Found a Pi at {0}{1}" -f $pick, $(if ($pv -contains $pick) { ' (PhotonVision answers on :5800)' } else { '' }))
            Add-Result 'PASS' 'Find the Pi' $pick
            return
        }
        Write-Fail 'No Pi found.'
        Write-Info 'Typical causes: Pi not powered/booted yet (wait ~1 minute), cable not DIRECTLY into the Pi, or ICS is off.'
        Write-Action 'To enable ICS (from docs/orangepi-internet-access.md):'
        Write-Info '  1. Win+R > ncpa.cpl   2. right-click your Wi-Fi > Properties > Sharing tab'
        Write-Info '  3. tick "Allow other network users to connect..." and pick the USB-Ethernet adapter'
        Write-Info '     (if already ticked: untick, OK, then tick again)   4. wait ~30 s for the Pi to get an address'
        Write-Info 'When you are done with the Pi, untick it again so the laptop returns to normal.'
        if ($Yes) { Add-Result 'FAIL' 'Find the Pi' 'not found'; Stop-Run 'Pi not found (non-interactive).' }
        $ans = Ask-Text 'Press Enter to scan again, type an address to try it, or "q" to quit' ''
        if ($ans -eq 'q') { Add-Result 'FAIL' 'Find the Pi' 'not found'; Stop-Run 'Stopped by user.' }
        if ($ans) {
            if (Test-TcpPort $ans 22 3000) { $script:Pi = $ans; Write-Pass "SSH answers at $ans"; Add-Result 'PASS' 'Find the Pi' $ans; return }
            Write-Fail "Nothing answers on port 22 at $ans."
        }
        if ($attempt -ge 10) { Add-Result 'FAIL' 'Find the Pi' 'not found'; Stop-Run 'Giving up after 10 scans.' }
    }
}

function Set-SshBase {
    $script:SshBase = @('-o', 'BatchMode=yes', '-o', 'ConnectTimeout=8', '-o', 'StrictHostKeyChecking=accept-new', '-o', 'ServerAliveInterval=15', '-i', $KeyPath, '-o', 'IdentitiesOnly=yes')
}

function Step-SshKey {
    Start-Step 'SSH key login' 'Key-based login lets the rest of this script (and later tooling) run without typing the Pi password again.'
    $pub = "$KeyPath.pub"
    if (-not (Test-Path $KeyPath)) {
        Write-Do "No key at $KeyPath - creating a new ed25519 key with no passphrase (it is only used for this Pi)."
        if (-not (Ask-YesNo 'Create it?' $true)) { Add-Result 'FAIL' 'SSH key' 'declined'; Stop-Run 'An SSH key is required.' }
        New-Item -ItemType Directory -Force (Split-Path $KeyPath) | Out-Null
        $r = Invoke-Native -File 'ssh-keygen' -Arguments @('-t', 'ed25519', '-N', '', '-C', "orangepi-bootstrap-$env:COMPUTERNAME", '-f', $KeyPath, '-q')
        if ($r.ExitCode -ne 0 -or -not (Test-Path $pub)) { Write-Fail ("ssh-keygen failed: " + $r.Err); Add-Result 'FAIL' 'SSH key' 'keygen failed'; Stop-Run 'Could not create key.' }
        Write-Pass "Created $KeyPath"
    } else { Write-Pass "Using existing key $KeyPath" }
    if (-not (Test-Path $pub)) {
        $r = Invoke-Native -File 'ssh-keygen' -Arguments @('-y', '-f', $KeyPath)
        if ($r.ExitCode -ne 0) { Write-Fail 'Public key missing and could not be derived (passphrase-protected key?).'; Add-Result 'FAIL' 'SSH key' 'no public key'; Stop-Run 'No public key.' }
        Set-Content -Path $pub -Value $r.Out.Trim() -Encoding ascii
    }
    Set-SshBase
    Write-Do "Testing key login as $User@$script:Pi ..."
    $r = Invoke-Pi 'echo ok' 20
    if ($r.ExitCode -eq 0 -and $r.Out -match 'ok') { Write-Pass 'Key login already works.'; Add-Result 'PASS' 'SSH key' 'key login works'; return }
    Write-Warn2 'Key login not accepted yet - installing the key.'
    if ($r.Err) { Write-Info ("ssh said: " + (($r.Err -split "`n")[0])) }
    Write-Action "ssh will now ask for the password of '$User' on the Pi. Type it at the ssh prompt (this script never sees it)."
    Write-Info '(PhotonVision images show a default login of photon/vision in their banner; the "pi" account must exist and be yours.)'
    $pubText = (Get-Content $pub -Raw).Trim()
    $remote = 'umask 077; mkdir -p ~/.ssh && touch ~/.ssh/authorized_keys && read -r k && (grep -qxF "$k" ~/.ssh/authorized_keys || echo "$k" >> ~/.ssh/authorized_keys) && chmod 600 ~/.ssh/authorized_keys'
    $a = @('-o', 'StrictHostKeyChecking=accept-new', '-o', 'ConnectTimeout=10', "$User@$script:Pi", $remote)
    $ins = Invoke-Native -File 'ssh' -Arguments $a -StdIn ($pubText + "`n") -Inherit -TimeoutSec 180
    $r = Invoke-Pi 'echo ok' 20
    if ($r.ExitCode -eq 0 -and $r.Out -match 'ok') { Write-Pass 'Key installed; key login works.'; Add-Result 'PASS' 'SSH key' 'installed and verified'; return }
    Write-Fail 'Key login still fails.'
    if ($r.Err) { Write-Info $r.Err }
    Write-Info "Check: user '$User' exists on the Pi, password was right, and /home/$User is not group/world-writable."
    Add-Result 'FAIL' 'SSH key' 'could not install key'
    Stop-Run 'SSH key login failed.'
}

function Step-Sudo {
    Start-Step 'Passwordless sudo' 'The Pi installer needs sudo for apt, systemd units and /etc. Passwordless sudo for this account lets it run unattended.'
    $r = Invoke-Pi 'sudo -n true && echo SUDO_OK' 20
    if ($r.Out -match 'SUDO_OK') { Write-Pass 'sudo already works without a password.'; Add-Result 'PASS' 'sudo' 'passwordless'; return }
    Write-Warn2 'sudo asks for a password.'
    Write-Info "This will write /etc/sudoers.d/90-$User-nopasswd (validated with visudo before it is activated)."
    if (-not (Ask-YesNo "Allow passwordless sudo for '$User' on this Pi?" $true)) {
        Add-Result 'SKIP' 'sudo' 'declined - installer will need a terminal for its sudo password'
        Write-Warn2 'Skipped. The unattended installer cannot run without it; use the interactive installer on the Pi instead.'
        $script:KnownIssue['sudo'] = $true
        return
    }
    Write-Action "ssh will ask for the sudo password of '$User' once."
    $cmd = "echo '$User ALL=(ALL) NOPASSWD:ALL' | sudo tee /tmp/90-$User-nopasswd >/dev/null && sudo visudo -cf /tmp/90-$User-nopasswd && sudo install -m 440 -o root -g root /tmp/90-$User-nopasswd /etc/sudoers.d/90-$User-nopasswd && rm -f /tmp/90-$User-nopasswd && echo SUDOERS_INSTALLED"
    $a = @($script:SshBase | Where-Object { $_ -ne 'BatchMode=yes' }) + @('-t', "$User@$script:Pi", $cmd)
    # BatchMode must be off for the password prompt; drop the "-o BatchMode=yes" pair.
    $a2 = @(); for ($i = 0; $i -lt $script:SshBase.Count; $i++) { if ($script:SshBase[$i] -eq '-o' -and $script:SshBase[$i + 1] -eq 'BatchMode=yes') { $i++ } else { $a2 += $script:SshBase[$i] } }
    $null = Invoke-Native -File 'ssh' -Arguments ($a2 + @('-t', "$User@$script:Pi", $cmd)) -Inherit -TimeoutSec 180
    $r = Invoke-Pi 'sudo -n true && echo SUDO_OK' 20
    if ($r.Out -match 'SUDO_OK') { Write-Pass 'Passwordless sudo enabled.'; Add-Result 'PASS' 'sudo' 'enabled'; return }
    Write-Fail 'sudo still needs a password.'
    Add-Result 'FAIL' 'sudo' 'not enabled'
    Stop-Run 'Passwordless sudo was not enabled.'
}

function Step-Health {
    Start-Step 'Pi health check' 'Confirms OS, Python, free disk, and whether the Pi can reach the internet (apt/pip need it for the first install only).'
    $r = Invoke-Pi 'hostname; . /etc/os-release; echo "$PRETTY_NAME"; python3 --version; df -h / | tail -1 | awk ''{print $4" free"}''; date -u +%FT%TZ; (curl -sI -m6 https://pypi.org | head -1) || true; test -x $HOME/.venv-ntpublisher/bin/python3 && $HOME/.venv-ntpublisher/bin/python3 -c "import ntcore; print(\"VENV_OK\")" 2>/dev/null || echo VENV_MISSING' 40
    if ($r.ExitCode -ne 0) { Write-Fail ("Could not query the Pi: " + $r.Err); Add-Result 'FAIL' 'Health' 'query failed'; Stop-Run 'Health check failed.' }
    $lines = @($r.Out -split "`r?`n" | Where-Object { $_.Trim() })
    Write-Info ("hostname {0} | {1} | {2} | {3} | clock {4}" -f $lines[0], $lines[1], $lines[2], $lines[3], $lines[4])
    $hasNet = ($r.Out -match 'HTTP/\d(\.\d)? [23]\d\d')
    $hasVenv = ($r.Out -match 'VENV_OK')
    $script:HasVenv = $hasVenv
    $freeGb = 0
    if ($lines[3] -match '([\d.]+)G') { $freeGb = [double]$Matches[1] }
    if ($freeGb -gt 0 -and $freeGb -lt 6) { Write-Warn2 "Only $freeGb GB free - the recorder keeps up to 5 GB per camera." }
    if ($hasNet) { Write-Pass 'Pi can reach the internet (pypi.org).' }
    elseif ($hasVenv) { Write-Warn2 'No internet on the Pi, but the venv already has ntcore - the installer can reuse it.' }
    else {
        Write-Fail 'The Pi has no internet and no Python venv yet: the installer cannot download pyntcore.'
        Write-Action 'Enable Internet Connection Sharing (see step 2 hints) or connect the Pi to a network with internet, then re-run.'
        Add-Result 'FAIL' 'Health' 'no internet'
        Stop-Run 'Pi needs internet for first install.'
    }
    $skew = $null
    if ($lines[4] -match '^\d{4}-') { $skew = [math]::Abs(([datetime]::Parse($lines[4]).ToUniversalTime() - [datetime]::UtcNow).TotalSeconds) }
    if ($skew -ne $null -and $skew -gt 300) { Write-Warn2 ("Pi clock differs from this laptop by {0:N0} s (normal off the robot network; the recorder labels sessions from the roboRIO clock)." -f $skew) }
    Add-Result 'PASS' 'Health' ("{0}; {1}; internet={2}" -f $lines[1], $lines[3], $hasNet)
}

function Step-Camera {
    Start-Step 'Camera and PhotonVision streams' 'The recorder taps PhotonVision''s own RAW MJPEG stream, so the camera must be activated in PhotonVision first.'
    $r = Invoke-Pi 'lsusb 2>/dev/null | grep -vi "root hub"; echo ---; ls /dev/video* 2>/dev/null | tr "\n" " "' 20
    $usb = @($r.Out -split '---')[0].Trim()
    if ($usb) { Write-Info ("USB devices: " + (($usb -split "`n") -join ' | ')) } else { Write-Warn2 'No USB camera visible via lsusb.' }
    $probe = 'for p in 1181 1182 1183 1184 1185 1186 1187 1188; do h=$(curl -s -m3 -D - -o /dev/null http://localhost:$p/stream.mjpg 2>/dev/null | head -1); case "$h" in *200*) echo $p;; esac; done'
    $ports = @()
    $tries = 0
    while ($true) {
        $tries++
        $r = Invoke-Pi $probe 40
        $ports = @($r.Out -split "`r?`n" | Where-Object { $_ -match '^\d+$' })
        if ($ports.Count -gt 0) { break }
        $pv = Test-TcpPort $script:Pi 5800 1500
        if (-not $pv) { Write-Fail 'PhotonVision does not answer on :5800 (is photonvision.service running?).'; Add-Result 'FAIL' 'Camera' 'PhotonVision down'; Stop-Run 'PhotonVision is not running.' }
        Write-Warn2 'PhotonVision is up but no camera stream is being served - the camera is not activated yet.'
        Write-Action ("Open http://{0}:5800/#/dashboard and click the 'camera matching tab' link (or the camera-config icon)," -f $script:Pi)
        Write-Info '  then click ACTIVATE on your USB camera. You should see it switch to "Active".'
        if ($tries -eq 1 -and -not $Yes) { try { Start-Process ("http://{0}:5800/#/dashboard" -f $script:Pi) } catch {} }
        if ($Yes) { Add-Result 'ACTION' 'Camera' 'camera not activated in PhotonVision'; Stop-Run 'Camera not activated.' }
        Wait-Enter 'Activate the camera, then'
        if ($tries -ge 8) { Add-Result 'FAIL' 'Camera' 'no stream'; Stop-Run 'No camera stream after several tries.' }
    }
    Write-Pass ("PhotonVision is serving streams on port(s): " + ($ports -join ', '))
    # PhotonVision numbers streams per camera: input (RAW) = 1181 + 2*i, output (PROCESSED) = 1182 + 2*i.
    $raw = @($ports | Where-Object { ([int]$_ - 1181) % 2 -eq 0 })
    $script:RawPorts = $raw
    Write-Info ("Raw (input) stream ports by PhotonVision's numbering: " + ($raw -join ', '))
    Write-Info ("Please confirm in the dashboard: set Stream Display to RAW and check the <img> URL port (http://{0}:5800/#/dashboard)." -f $script:Pi)
    Add-Result 'PASS' 'Camera' ("streams on " + ($ports -join ','))
}

function Step-PhotonTeam {
    Start-Step 'PhotonVision team number' 'PhotonVision must know team 1405 so it connects to the roboRIO''s NetworkTables on the robot.'
    $py = 'import sqlite3,json;c=sqlite3.connect("file:/opt/photonvision/photonvision_config/photon.sqlite?mode=ro",uri=True);r=[json.loads(x[1]) for x in c.execute("select * from global") if x[0]=="networkConfig"];print(r[0].get("ntServerAddress") if r else "NONE")'
    $r = Invoke-Pi ("python3 -c '" + $py + "'") 20
    $val = $r.Out.Trim()
    if ($val -eq '1405') { Write-Pass 'PhotonVision team number is 1405.'; Add-Result 'PASS' 'PhotonVision team' '1405'; return }
    Write-Warn2 ("PhotonVision ntServerAddress is '{0}' (expected 1405)." -f $val)
    Write-Action ("Open http://{0}:5800/#/settings, set 'Team Number/NetworkTables Server Address' to 1405 and press SAVE." -f $script:Pi)
    Write-Info 'Leave IP Assignment on DHCP unless you have a reason; changing it can drop your connection to the Pi.'
    Add-Result 'ACTION' 'PhotonVision team' ("currently '$val' - set to 1405 in the web UI")
}

function Step-Plan {
    Start-Step 'Decide this board''s identity' 'Every board on the robot needs a DISTINCT NetworkTables name, and each camera needs a name and its RAW stream URL.'
    $cur = ''
    $r = Invoke-Pi 'sudo cat /etc/default/orangepi-nt-publisher 2>/dev/null | sed -n "s/^ORANGEPI_METRICS_NAME=//p" | tail -1' 20
    $cur = $r.Out.Trim()
    if (-not $BoardName) {
        Write-Info 'Examples: LeftPi, RightPi, VisionFront, BenchPi. Letters, digits, _ and - only.'
        $BoardName = Ask-Text 'Board NT name' $cur
    }
    if ($BoardName -notmatch '^[A-Za-z0-9_-]+$') { Add-Result 'FAIL' 'Plan' 'bad board name'; Stop-Run "Board name '$BoardName' is invalid (letters, digits, _ and - only)." }
    $script:Board = $BoardName
    if (-not $Cameras -or $Cameras.Count -eq 0) {
        Write-Info 'Camera instance names for THIS board (the recordings folder is named after it), e.g. left, right, front.'
        $s = Ask-Text 'Camera instance name(s), space separated' ''
        $Cameras = @($s -split '\s+' | Where-Object { $_ })
    }
    if (-not $Cameras -or $Cameras.Count -eq 0) { Write-Warn2 'No cameras entered - only the metrics publisher will be installed.' }
    foreach ($c in $Cameras) { if ($c -notmatch '^[A-Za-z0-9_-]+$') { Add-Result 'FAIL' 'Plan' 'bad camera name'; Stop-Run "Camera name '$c' is invalid." } }
    $script:CameraList = @($Cameras)
    $script:Streams = @{}
    $i = 0
    foreach ($c in $script:CameraList) {
        $default = 'http://localhost:1181/stream.mjpg'
        if ($script:RawPorts -and $script:RawPorts.Count -gt $i) { $default = "http://localhost:$($script:RawPorts[$i])/stream.mjpg" }
        if ($StreamUrls -and $StreamUrls.ContainsKey($c)) { $url = [string]$StreamUrls[$c] }
        else { $url = Ask-Text "RAW stream URL for '$c' (as the Pi sees it)" $default }
        if ($url -notmatch '^https?://[^\s"''\\]+$') { Add-Result 'FAIL' 'Plan' 'bad URL'; Stop-Run "Stream URL '$url' is not a plain http(s) URL." }
        $script:Streams[$c] = $url
        $i++
    }
    Write-Host ''
    Write-Info ("Board NT name : {0}  (metrics at /OrangePi/{0}/)" -f $script:Board)
    foreach ($c in $script:CameraList) { Write-Info ("Camera '{0}'  : {1}  -> recordings in ~/vision-recordings/{0}/" -f $c, $script:Streams[$c]) }
    if (-not (Ask-YesNo 'Install with these settings?' $true)) { Add-Result 'SKIP' 'Plan' 'user declined'; Stop-Run 'Stopped by user before installing.' }
    Add-Result 'PASS' 'Plan' ("{0}; cameras: {1}" -f $script:Board, ($script:CameraList -join ', '))
}

function Step-Copy {
    Start-Step 'Copy the coprocessor scripts' 'Puts the scripts and unit files where the installer expects them: /home/pi/coprocessor.'
    $files = @('setup-orangepi.sh', 'orangepi-nt-publisher.py', 'orangepi-nt-publisher.service', 'orangepi-vision-recorder.py', 'orangepi-vision-recorder@.service') | ForEach-Object { Join-Path $script:CoprocessorDir $_ }
    foreach ($opt in 'enable-fan.sh', 'check-fan.sh', 'README.md') { $p = Join-Path $script:CoprocessorDir $opt; if (Test-Path $p) { $files += $p } }
    $r = Invoke-Pi 'mkdir -p /home/pi/coprocessor /home/pi/coprocessor/sim' 20
    if ($r.ExitCode -ne 0) { Write-Fail $r.Err; Add-Result 'FAIL' 'Copy' 'mkdir failed'; Stop-Run 'Could not create /home/pi/coprocessor.' }
    $scpBase = @($script:SshBase) + @('-q')
    $x = Invoke-Native -File 'scp' -Arguments ($scpBase + $files + @("$User@${script:Pi}:/home/pi/coprocessor/")) -TimeoutSec 120
    if ($x.ExitCode -ne 0) { Write-Fail ("scp failed: " + (Remove-PiBanner $x.Err)); Add-Result 'FAIL' 'Copy' 'scp failed'; Stop-Run 'Copy failed.' }
    $simDir = Join-Path $script:CoprocessorDir 'sim'
    $simFiles = @()
    if (Test-Path $simDir) { $simFiles = @(Get-ChildItem $simDir -File -Include *.py, *.md -Recurse | ForEach-Object { $_.FullName }) }
    if ($simFiles.Count -gt 0) {
        $x = Invoke-Native -File 'scp' -Arguments ($scpBase + $simFiles + @("$User@${script:Pi}:/home/pi/coprocessor/sim/")) -TimeoutSec 120
        if ($x.ExitCode -ne 0) { Write-Warn2 ("sim files not copied: " + (Remove-PiBanner $x.Err)) } else { Write-Info ("Also copied {0} simulation file(s) to coprocessor/sim/." -f $simFiles.Count) }
    }
    $r = Invoke-Pi "sed -i 's/\r`$//' /home/pi/coprocessor/*.sh /home/pi/coprocessor/*.py /home/pi/coprocessor/*.service 2>/dev/null; sed -i 's/\r`$//' /home/pi/coprocessor/sim/*.py 2>/dev/null; ls /home/pi/coprocessor | tr '\n' ' '" 20
    Write-Pass ("Copied. On the Pi: " + $r.Out.Trim())
    Add-Result 'PASS' 'Copy' ("{0} files" -f $files.Count)
}

function Step-Install {
    Start-Step 'Run the Pi installer' 'Runs setup-orangepi.sh unattended: creates the Python venv, installs pyntcore, installs and starts the services.'
    if ($script:KnownIssue['sudo']) { Add-Result 'SKIP' 'Install' 'needs passwordless sudo'; Write-Warn2 'Skipped (no passwordless sudo).'; Write-Info 'Run it by hand: ssh pi@<ip>  then  cd ~/coprocessor && bash setup-orangepi.sh'; return }
    $choice = if ($script:CameraList.Count -gt 0) { 3 } else { 1 }
    $streams = (($script:CameraList | ForEach-Object { "{0}={1}" -f $_, $script:Streams[$_] }) -join ' ')
    $cmd = "cd /home/pi/coprocessor && SETUP_UNATTENDED=1 SETUP_CHOICE=$choice SETUP_BOARD_NAME='$($script:Board)' SETUP_CAMERAS='$($script:CameraList -join ' ')' SETUP_STREAMS='$streams' bash setup-orangepi.sh 2>&1"
    Write-Do 'Installing (first run downloads packages; this can take a few minutes)...'
    $r = Invoke-Pi $cmd 900
    $lines = @($r.Out -split "`r?`n")
    if ($r.ExitCode -ne 0) {
        Write-Fail ("Installer exited with code {0}. Last output:" -f $r.ExitCode)
        $lines | Select-Object -Last 40 | ForEach-Object { Write-Host ('    ' + $_) -ForegroundColor DarkGray }
        if ($r.Err) { Write-Info $r.Err }
        Write-Info 'Changes already made are kept. Fix the cause above and re-run this script (it will skip what is done).'
        Add-Result 'FAIL' 'Install' ("exit $($r.ExitCode)")
        Stop-Run 'Installer failed.'
    }
    $lines | Where-Object { $_ -match 'ntcore import|Metrics namespace|Stream responds|WARNING|Setup checks passed|Created symlink' } | ForEach-Object { Write-Info $_ }
    if ($r.Out -match 'WARNING: camera stream check failed') { Write-Warn2 'The installer could not open a camera stream URL (see above); the recorder will keep retrying.' }
    Write-Pass 'Installer finished without errors.'
    Add-Result 'PASS' 'Install' 'setup-orangepi.sh ok'
}

function Step-Verify {
    Start-Step 'Verify the install' 'Independent checks that the services are running with the right settings.'
    $ok = $true
    $r = Invoke-Pi 'bash /home/pi/coprocessor/setup-orangepi.sh --status 2>&1 | tail -4; echo "STATUS_EXIT=${PIPESTATUS[0]}"' 60
    if ($r.Out -match 'STATUS_EXIT=0') { Write-Pass 'setup-orangepi.sh --status reports healthy.' } else { Write-Fail 'setup-orangepi.sh --status reported a problem:'; $r.Out -split "`n" | ForEach-Object { Write-Info $_ }; $ok = $false }
    $units = @('orangepi-nt-publisher.service') + ($script:CameraList | ForEach-Object { "orangepi-vision-recorder@$_.service" })
    foreach ($u in $units) {
        $s = (Invoke-Pi "systemctl is-active $u; systemctl is-enabled $u; systemctl show $u -p NRestarts --value" 20).Out -split "`r?`n"
        if ($s[0] -eq 'active' -and $s[1] -eq 'enabled') { Write-Pass ("{0}: active, enabled at boot, restarts={1}" -f $u, $s[2]) } else { Write-Fail ("{0}: {1} / {2}" -f $u, $s[0], $s[1]); $ok = $false }
    }
    foreach ($c in $script:CameraList) {
        $env = (Invoke-Pi "sudo cat /etc/orangepi-vision-recorder/$c.env" 20).Out
        Write-Info ("{0}.env -> {1}" -f $c, (($env -split "`r?`n" | Where-Object { $_.Trim() }) -join '; '))
    }
    if ($ok) { Add-Result 'PASS' 'Verify' 'services healthy' } else { Add-Result 'FAIL' 'Verify' 'see above' }
}

function Show-Summary {
    Write-Banner 'Summary'
    foreach ($r in $script:Results) {
        $color = switch ($r.Status) { 'PASS' { 'Green' } 'FAIL' { 'Red' } 'ACTION' { 'Magenta' } default { 'Yellow' } }
        Write-Host ("  {0,2}  {1,-7} {2,-26} {3}" -f $r.Step, $r.Status, $r.Title, $r.Detail) -ForegroundColor $color
    }
    $failed = @($script:Results | Where-Object { $_.Status -eq 'FAIL' })
    $actions = @($script:Results | Where-Object { $_.Status -eq 'ACTION' -or $_.Status -eq 'SKIP' })
    Write-Host ''
    if ($failed.Count -gt 0) {
        Write-Host '  Not finished: fix the FAIL line(s) above and run this script again - it skips what is already done.' -ForegroundColor Red
    } elseif ($actions.Count -gt 0) {
        Write-Host '  Installed, but a few things still need you (see ACTION/SKIP lines).' -ForegroundColor Yellow
    } else {
        Write-Host '  This Pi is set up.' -ForegroundColor Green
    }
    if ($script:Pi) {
        Write-Info ("Pi: {0}@{1}   key: {2}" -f $User, $script:Pi, $KeyPath)
        Write-Info 'Next: bench-verify the recorder with no robot using coprocessor\sim\Run-SimulatedMatch.ps1 (see coprocessor\sim\README.md).'
        Write-Info 'When done with the Pi, switch Internet Connection Sharing off again.'
    }
}

# ---------------------------------------------------------------- main
Write-Host ("Bootstrap-OrangePi {0} - guided one-time setup of a team Orange Pi (runs on this laptop)" -f $script:Version) -ForegroundColor Cyan
Write-Host 'Not to be confused with setup-orangepi.sh, which runs ON the Pi - this script drives it for you.' -ForegroundColor DarkGray
$exitCode = 0
try {
    Step-Preflight
    Step-FindPi
    Step-SshKey
    Step-Sudo
    Step-Health
    Step-Camera
    Step-PhotonTeam
    Step-Plan
    Step-Copy
    Step-Install
    Step-Verify
} catch [StepAbort] {
    Write-Host ''
    Write-Fail $_.Exception.Message
    $exitCode = 1
} catch {
    Write-Host ''
    Write-Fail ("Unexpected error: " + $_.Exception.Message)
    Write-Info $_.ScriptStackTrace
    Add-Result 'FAIL' 'Unexpected error' $_.Exception.Message
    $exitCode = 2
}
Show-Summary
if (@($script:Results | Where-Object { $_.Status -eq 'FAIL' }).Count -gt 0 -and $exitCode -eq 0) { $exitCode = 1 }
exit $exitCode
