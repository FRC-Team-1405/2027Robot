# No Pi or Pester required. Run with Windows PowerShell 5.1 or PowerShell 7.
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../Bootstrap-OrangePi.ps1'
$tokens = $null; $parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
# Load only functions; never execute the interactive bootstrap entry point.
$functions = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)
. (Join-Path $PSScriptRoot '../lib/Wizard.ps1')   # Resolve-RobotConfig and the wizard helpers
foreach ($name in 'ConvertTo-NativeArgument', 'Invoke-Native', 'Step-FindPi') {
    $definition = ($functions | Where-Object { $_.Name -eq $name }).Extent.Text
    Invoke-Expression $definition
    if ($name -eq 'Invoke-Native') {
        # Exercise the production .NET Framework fallback even when testing on PS7.
        $legacy = $definition.Replace('function Invoke-Native {', 'function Invoke-NativeLegacy {')
        $legacy = $legacy.Replace("if (`$null -ne `$psi.PSObject.Properties['ArgumentList'])", 'if ($false)')
        Invoke-Expression $legacy
    }
}
function Assert-Equal($Expected, $Actual, [string]$Label) {
    if ($Expected -cne $Actual) { throw "$Label : expected <$Expected>, got <$Actual>" }
}

# Exact Windows escaping cases (including backslashes before quotes and at the end).
$cases = @(
    @('', '""'),
    @('plain', 'plain'),
    @('C:\Users\Team Member\.ssh\key', '"C:\Users\Team Member\.ssh\key"'),
    @('say "hello"', '"say \"hello\""'),
    @('C:\space here\', '"C:\space here\\"'),
    @('a\"b', '"a\\\"b"')
)
foreach ($case in $cases) { Assert-Equal $case[1] (ConvertTo-NativeArgument $case[0]) 'Windows escaping' }

$python = Get-Command python, python3 -CommandType Application -ErrorAction SilentlyContinue | Select-Object -First 1
if (-not $python) { throw 'Python 3 is required for the argv round-trip check.' }
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("bootstrap regression " + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    foreach ($runner in 'Invoke-Native', 'Invoke-NativeLegacy') {
        $values = @('', 'two words', 'say "hello"', 'a\"b', 'C:\space here\', 'dollar$ & semicolon;', '')
        $r = & $runner -File $python.Source -Arguments (@('-c', 'import json,sys; print(json.dumps(sys.argv[1:]))') + $values)
        Assert-Equal 0 $r.ExitCode "$runner argv exit code"
        $actual = @($r.Out | ConvertFrom-Json)
        Assert-Equal $values.Count $actual.Count "$runner argument count"
        for ($i = 0; $i -lt $values.Count; $i++) { Assert-Equal $values[$i] $actual[$i] "$runner argv[$i]" }

        # Real key generation with an empty passphrase and spaces in the key path.
        $key = Join-Path $tempDir "$runner key"
        $r = & $runner -File 'ssh-keygen' -Arguments @('-t', 'ed25519', '-N', '', '-C', 'bootstrap regression', '-f', $key, '-q') -TimeoutSec 10
        Assert-Equal 0 $r.ExitCode "$runner key generation: $($r.Err)"
        if (-not (Test-Path "$key.pub")) { throw "$runner did not create the public key" }
        $r = & $runner -File 'ssh-keygen' -Arguments @('-y', '-P', '', '-f', $key) -TimeoutSec 10
        Assert-Equal 0 $r.ExitCode "$runner read unencrypted key"
        $public = (Get-Content "$key.pub" -Raw) -split ' '
        Assert-Equal ($public[0..1] -join ' ') (($r.Out.Trim() -split ' ')[0..1] -join ' ') "$runner public key"
        Write-Host "PASS: $runner argv round trip and real ssh-keygen"
    }
} finally { Remove-Item -Recurse -Force $tempDir }

# Deterministic discovery regression: one result must stay a hostname, not 'p'.
function Start-Step { param($Title, $Why) }
function Write-Do { param($Text) }
function Write-Info { param($Text) }
function Write-Pass { param($Text) }
function Write-Fail { param($Text) }
function Write-Action { param($Text) }
function Write-Warn2 { param($Text) }
function Add-Result { param($Status, $Title, $Detail) }
function Get-NetIPAddress { param($AddressFamily, $ErrorAction) }
function Find-OpenPort { param($Hosts, $Port) $script:FoundHosts }
function Test-TcpPort { param($HostName, $Port, $TimeoutMs) $script:PhotonAnswers }
function Ask-Text { param($Question, $Default) $Default }
function Stop-Run { param($Message) throw $Message }
$Address = ''; $Yes = $true
foreach ($hostList in @(@('photonvision.local'), @('192.168.137.241'), @('photonvision.local', '192.168.1.252'))) {
    foreach ($pv in $false, $true) {
        $script:FoundHosts = $hostList; $script:PhotonAnswers = $pv; $script:Pi = $null
        Step-FindPi
        Assert-Equal $hostList[0] $script:Pi 'Discovered hostname'
    }
}
$script:FoundHosts = @(); $script:Pi = $null
try { Step-FindPi; throw 'Expected discovery failure' } catch {
    Assert-Equal 'Pi not found (non-interactive).' $_.Exception.Message 'No-host discovery'
}
Write-Host 'PASS: discovery with zero, one, and multiple hosts'

# robots.json addresses are tried in order before searching.
$script:HostCandidates = @('LeftPi', 'LeftPi.local'); $script:ConfigLabel = 'robots.json, robot test'
function Test-TcpPort { param($HostName, $Port, $TimeoutMs) $HostName -eq 'LeftPi.local' }
$script:Pi = $null; $Address = ''
Step-FindPi
Assert-Equal 'LeftPi.local' $script:Pi 'robots.json host fallback'
$script:HostCandidates = @()
Write-Host 'PASS: robots.json host candidates'

# robots.json: the committed file parses and names both 2027 boards.
$real = Resolve-RobotConfig -Path (Join-Path $PSScriptRoot '../robots.json') -Addr 'leftpi'
Assert-Equal '2027' $real.RobotName 'default robot'
Assert-Equal 'LeftPi' $real.Board.name 'board by address, any case'
Assert-Equal 'LeftCam' $real.Board.cameras[0].name 'LeftPi camera'
Assert-Equal 'http://localhost:1181/stream.mjpg' $real.Board.cameras[0].stream 'LeftPi stream'
Assert-Equal 'RightCam' (Resolve-RobotConfig -Path (Join-Path $PSScriptRoot '../robots.json') -Board 'RightPi').Board.cameras[0].name 'RightPi camera'

# Lookups by name, host and robot; unknown boards fall back to prompting; bad input stops.
$tempDir = Join-Path ([System.IO.Path]::GetTempPath()) ("bootstrap robots " + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $tempDir | Out-Null
try {
    $file = Join-Path $tempDir 'robots.json'
    Set-Content -Path $file -Encoding ascii -Value @'
{ "defaultRobot": "a",
  "robots": {
    "a": { "boards": [ { "name": "FrontPi", "hosts": ["10.14.5.11", "front.local"], "cameras": [ { "name": "Front", "stream": "http://localhost:1181/stream.mjpg" } ] } ] },
    "b": { "boards": [ { "name": "FrontPi", "hosts": ["10.14.5.21"], "cameras": [ { "name": "Front", "stream": "http://localhost:1183/stream.mjpg" },
                                                                        { "name": "Rear",  "stream": "http://localhost:1185/stream.mjpg" } ] } ] }
  } }
'@
    Assert-Equal 'FrontPi' (Resolve-RobotConfig -Path $file -Addr 'front.local').Board.name 'board by host'
    Assert-Equal 'FrontPi' (Resolve-RobotConfig -Path $file -Board 'frontpi').Board.name 'board by name, any case'
    $b = (Resolve-RobotConfig -Path $file -RobotName 'B' -Board 'FrontPi').Board
    Assert-Equal 2 @($b.cameras).Count 'robot b cameras'
    Assert-Equal 'http://localhost:1185/stream.mjpg' $b.cameras[1].stream 'robot b rear stream'
    $none = Resolve-RobotConfig -Path $file -Addr '192.168.137.50'
    Assert-Equal $true ($null -ne $none -and $null -eq $none.Board) 'unknown address: no board, no error'
    Assert-Equal $true ($null -eq (Resolve-RobotConfig -Path (Join-Path $tempDir 'missing.json'))) 'no file, not required'
    foreach ($bad in @(@{ RobotName = 'nope' }, @{ Path = (Join-Path $tempDir 'missing.json'); Required = $true })) {
        $a = @{ Path = $file }; foreach ($k in $bad.Keys) { $a[$k] = $bad[$k] }
        $threw = $false; try { Resolve-RobotConfig @a | Out-Null } catch { $threw = $true }
        Assert-Equal $true $threw ("stops on " + ($bad.Keys -join ','))
    }
    Set-Content -Path $file -Encoding ascii -Value '{ "defaultRobot": "a", "robots": { "a": { "boards": [ { "name": "bad name" } ] } } }'
    $threw = $false; try { Resolve-RobotConfig -Path $file | Out-Null } catch { $threw = $true }
    Assert-Equal $true $threw 'stops on an invalid board name'
} finally { Remove-Item -Recurse -Force $tempDir }
Write-Host 'PASS: robots.json lookups'

# Wizard menus: Enter takes the default, a number picks, junk is asked again.
$script:Answers = New-Object System.Collections.Queue
function Read-Host { param($Prompt) $script:Answers.Dequeue() }
function Write-Host { }
function Set-Answers([string[]]$a) { $script:Answers.Clear(); foreach ($x in $a) { $script:Answers.Enqueue($x) } }
$opts = @(@{ Label = 'Every board'; Value = '__all__' }, @{ Label = 'LeftPi only'; Value = 'LeftPi' }, @{ Label = 'No value' })
Set-Answers @('');         Assert-Equal '__all__' (Select-Choice -Title t -Options $opts) 'Enter = default 1'
Set-Answers @('');         Assert-Equal 'LeftPi' (Select-Choice -Title t -Options $opts -Default 2) 'Enter = default 2'
Set-Answers @('7', 'x', '2'); Assert-Equal 'LeftPi' (Select-Choice -Title t -Options $opts) 'bad answers are asked again'
Set-Answers @('3');        Assert-Equal 'No value' (Select-Choice -Title t -Options $opts) 'label when no value'
Set-Answers @('', 'bad addr', '10.14.5.11')
Assert-Equal '' (Read-Answer -Prompt p -Pattern '[A-Za-z0-9._:-]*') 'empty answer allowed'
Assert-Equal '10.14.5.11' (Read-Answer -Prompt p -Pattern '[A-Za-z0-9._:-]*') 'pattern re-asks'
$cfg = Resolve-RobotConfig -Path (Join-Path $PSScriptRoot '../robots.json')
Set-Answers @('2'); Assert-Equal 'RightPi' (Select-Board $cfg).name 'Select-Board returns the board'
Set-Answers @('3'); Assert-Equal $true ($null -eq (Select-Board $cfg)) 'Select-Board other'
Remove-Item function:Read-Host, function:Write-Host
Write-Host 'PASS: wizard menus'
