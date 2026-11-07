# Shared start-up wizard for the laptop-side coprocessor scripts (Bootstrap-OrangePi.ps1,
# sim\Run-SimulatedMatch.ps1, sim\Run-SimRobotMatch.ps1). Dot-source it:
#     . (Join-Path $PSScriptRoot 'lib\Wizard.ps1')
# Every script works the same way: run it with no options and it asks, with numbered choices and a
# default you get by pressing Enter; at the end it prints the equivalent command line, so the next
# run can skip the questions. Options given on the command line are never asked about.
# Works on Windows PowerShell 5.1 and PowerShell 7. ASCII only (5.1 reads scripts as ANSI).

# True when a person can answer questions (not redirected input, not -NonInteractive).
# COPROCESSOR_WIZARD=off never asks (automation); =on always asks, reading answers from stdin
# (used to test the wizard by piping answers in).
function Test-CanAsk {
    if ($env:COPROCESSOR_WIZARD -ieq 'off') { return $false }
    if ($env:COPROCESSOR_WIZARD -ieq 'on') { return $true }
    try {
        if ([Console]::IsInputRedirected) { return $false }
    } catch {}
    $noni = [Environment]::GetCommandLineArgs() | Where-Object { $_ -match '^-noni' }
    return -not $noni
}

# Numbered menu. $Options: hashtables/objects with Label, optional Detail and Value.
# Returns the chosen option's Value (or its Label when it has none). 'q' quits the script.
function Select-Choice {
    param([string]$Title, [object[]]$Options, [int]$Default = 1, [string]$Why)
    if ($Options.Count -eq 0) { throw "Select-Choice '$Title': no options." }
    if ($Default -lt 1 -or $Default -gt $Options.Count) { $Default = 1 }
    Write-Host ''
    Write-Host ('  ' + $Title) -ForegroundColor Cyan
    if ($Why) { Write-Host ('  ' + $Why) -ForegroundColor DarkGray }
    for ($i = 0; $i -lt $Options.Count; $i++) {
        $o = $Options[$i]
        $mark = if ($i + 1 -eq $Default) { '  (default)' } else { '' }
        Write-Host ('    {0}) {1}{2}' -f ($i + 1), $o.Label, $mark) -ForegroundColor White
        if ($o.Detail) { Write-Host ('       ' + $o.Detail) -ForegroundColor DarkGray }
    }
    while ($true) {
        $a = Read-Host ('  Choose 1-{0}, Enter for {1}, q to quit' -f $Options.Count, $Default)
        if ($null -eq $a) { Write-Host '  No more input.' -ForegroundColor Yellow; exit 1 }
        $a = $a.Trim()
        if ($a -eq '') { $n = $Default }
        elseif ($a -ieq 'q') { Write-Host '  Stopped.' -ForegroundColor Yellow; exit 1 }
        elseif ($a -match '^\d+$' -and [int]$a -ge 1 -and [int]$a -le $Options.Count) { $n = [int]$a }
        else { Write-Host ("  '{0}' isn't one of the choices." -f $a) -ForegroundColor Yellow; continue }
        $pick = $Options[$n - 1]
        if ($null -ne $pick.Value) { return $pick.Value }
        return $pick.Label
    }
}

# Free-text question with a default. $Pattern, when given, must match the whole answer.
function Read-Answer {
    param([string]$Prompt, [string]$Default = '', [string]$Pattern, [string]$Hint)
    while ($true) {
        $shown = if ($Default) { " [$Default]" } else { '' }
        $a = Read-Host ('  {0}{1}' -f $Prompt, $shown)
        if ($null -eq $a) { Write-Host '  No more input.' -ForegroundColor Yellow; exit 1 }
        $a = $a.Trim()
        if ($a -eq '') { $a = $Default }
        if ($a -ieq 'q') { Write-Host '  Stopped.' -ForegroundColor Yellow; exit 1 }
        if (-not $Pattern -or $a -match "^(?:$Pattern)$") { return $a }
        Write-Host ('  ' + $(if ($Hint) { $Hint } else { "That doesn't look right." })) -ForegroundColor Yellow
    }
}

# "Same as:  .\Script.ps1 -All -Yes" -- shows what the answers mean as options.
function Show-EquivalentCommand {
    param([string]$ScriptName, [System.Collections.IDictionary]$Options)
    $parts = @(".\$ScriptName")
    foreach ($k in $Options.Keys) {
        $v = $Options[$k]
        if ($v -is [bool] -or $v -is [System.Management.Automation.SwitchParameter]) { if ($v) { $parts += "-$k" } }
        elseif ($null -ne $v -and "$v" -ne '') {
            $s = "$v"
            if ($s -match '[\s'',;]') { $s = "'" + ($s -replace "'", "''") + "'" }
            $parts += "-$k $s"
        }
    }
    Write-Host ''
    Write-Host ('  Same as:  ' + ($parts -join ' ')) -ForegroundColor Green
    Write-Host ('  (run that next time to skip these questions; Get-Help .\{0} -Full lists every option)' -f $ScriptName) -ForegroundColor DarkGray
}

# ---------------------------------------------------------------- robots.json
# Default location: coprocessor\robots.json (this file lives in coprocessor\lib).
function Get-RobotsPath { Join-Path (Split-Path $PSScriptRoot -Parent) 'robots.json' }

# Returns @{ RobotName; Robot; Board; Robots } where Board is the board named by -Board, or whose
# name/host is -Addr (case-insensitive), else $null. Returns $null when there is no robots.json and
# none was required. Throws with a readable message on a bad file or an unknown robot.
function Resolve-RobotConfig {
    param([string]$Path, [string]$RobotName, [string]$Board, [string]$Addr, [bool]$Required)
    if (-not $Path) { $Path = Get-RobotsPath }
    if (-not (Test-Path $Path)) {
        if ($Required) { throw "robots.json not found at '$Path'." }
        return $null
    }
    try { $cfg = Get-Content -Raw -Path $Path | ConvertFrom-Json } catch { throw ("{0} is not valid JSON: {1}" -f $Path, $_.Exception.Message) }
    if (-not $RobotName) { $RobotName = [string]$cfg.defaultRobot }
    $all = @($cfg.robots.PSObject.Properties)
    $prop = $all | Where-Object { $_.Name -ieq $RobotName } | Select-Object -First 1
    if (-not $prop) { throw ("No robot '{0}' in {1} (known: {2})." -f $RobotName, $Path, (($all | ForEach-Object { $_.Name }) -join ', ')) }
    $r = $prop.Value
    $boards = @($r.boards)
    foreach ($b in $boards) {
        if (-not $b.name -or $b.name -notmatch '^[A-Za-z0-9_-]+$') { throw ("{0}: robot '{1}' has a board with a missing or invalid name." -f $Path, $prop.Name) }
        foreach ($c in @($b.cameras)) {
            if (-not $c.name -or $c.name -notmatch '^[A-Za-z0-9_-]+$') { throw ("{0}: board '{1}' has a camera with a missing or invalid name." -f $Path, $b.name) }
        }
    }
    $match = $null
    if ($Board) {
        $match = $boards | Where-Object { $_.name -ieq $Board } | Select-Object -First 1
    } elseif ($Addr) {
        $match = $boards | Where-Object { $_.name -ieq $Addr -or (@($_.hosts) -icontains $Addr) } | Select-Object -First 1
    }
    return [pscustomobject]@{ RobotName = $prop.Name; Robot = $r; Board = $match; Robots = $all; Path = $Path }
}

# Wizard step: which robot (only asked when robots.json has more than one).
function Select-Robot {
    param($Config)
    $robots = @($Config.Robots)
    if ($robots.Count -le 1) { return $Config }
    $opts = @(); $def = 1
    for ($i = 0; $i -lt $robots.Count; $i++) {
        $p = $robots[$i]
        $names = (@($p.Value.boards) | ForEach-Object { $_.name }) -join ', '
        $opts += @{ Label = $p.Name; Detail = ("{0}  boards: {1}" -f $p.Value.description, $names).Trim(); Value = $p.Name }
        if ($p.Name -ieq $Config.RobotName) { $def = $i + 1 }
    }
    $name = Select-Choice -Title 'Which robot?' -Options $opts -Default $def -Why ('From ' + $Config.Path)
    return Resolve-RobotConfig -Path $Config.Path -RobotName $name
}

# One line describing a board: "camera LeftCam | Pi at LeftPi.local".
function Format-Board {
    param($Board)
    $cams = @($Board.cameras | ForEach-Object { $_.name })
    $hosts = (@($Board.hosts) | Where-Object { $_ }) -join ' or '
    $camText = switch ($cams.Count) { 0 { 'no cameras' } 1 { 'camera ' + $cams[0] } default { 'cameras ' + ($cams -join ', ') } }
    return ("{0} | Pi at {1}" -f $camText, $(if ($hosts) { $hosts } else { $Board.name }))
}

# Wizard step: one board of the robot, or "another Pi". Returns the board object, or $null for
# "another Pi" (the caller then asks for an address).
function Select-Board {
    param($Config, [string]$Title = 'Which Orange Pi?', [string]$OtherLabel = 'A Pi that is not in robots.json (type its address)')
    $opts = @()
    foreach ($b in @($Config.Robot.boards)) { $opts += @{ Label = $b.name; Detail = (Format-Board $b); Value = $b } }
    $opts += @{ Label = $OtherLabel; Value = '__other__' }
    $pick = Select-Choice -Title $Title -Options $opts -Why ("Robot '{0}' in robots.json" -f $Config.RobotName)
    if ($pick -is [string] -and $pick -eq '__other__') { return $null }
    return $pick
}
