# No Pi or Pester required. Run with Windows PowerShell 5.1 or PowerShell 7.
$ErrorActionPreference = 'Stop'
$source = Join-Path $PSScriptRoot '../Bootstrap-OrangePi.ps1'
$tokens = $null; $parseErrors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count) { throw ($parseErrors | Out-String) }
# Load only functions; never execute the interactive bootstrap entry point.
$functions = $ast.FindAll({ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] }, $false)
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
