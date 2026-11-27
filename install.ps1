# ===============================================================
#  Coda installer for Windows - https://github.com/sebamuhr/Coda
#
#  In PowerShell:
#    irm https://raw.githubusercontent.com/sebamuhr/Coda/main/install.ps1 | iex
#
#  With options:
#    & ([scriptblock]::Create((irm https://raw.githubusercontent.com/sebamuhr/Coda/main/install.ps1))) -Engine claude
#
#  Safe to run again: it updates the existing install in place and keeps
#  your settings. No administrator rights needed; everything is per user.
#
#  Options:
#    -Yes            no questions; use defaults
#    -Engine NAME    coding agent "Call Coda" opens: claude, codex,
#                    cursor-agent, gemini or aider
#    -NoAutostart    don't start Coda on login
#    -NoStart        don't start Coda when the install finishes
#
#  Everything goes in:
#    %LOCALAPPDATA%\Coda    app, Python environment, the coda command
#    %APPDATA%\Coda         your settings
#  Remove it all with:  coda uninstall
# ===============================================================
param(
    [switch]$Yes,
    [string]$Engine = '',
    [switch]$NoAutostart,
    [switch]$NoStart
)
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'   # makes downloads much faster in Windows PowerShell

$Repo    = 'sebamuhr/Coda'
$Branch  = if ($env:CODA_BRANCH) { $env:CODA_BRANCH } else { 'main' }
$DataDir = Join-Path $env:LOCALAPPDATA 'Coda'
$AppDir  = Join-Path $DataDir 'app'
$Venv    = Join-Path $DataDir 'venv'
$VPy     = Join-Path $Venv 'Scripts\python.exe'
$VPyw    = Join-Path $Venv 'Scripts\pythonw.exe'
$Engines = @('claude', 'codex', 'cursor-agent', 'gemini', 'aider')

function Step($n, $text) { Write-Host ''; Write-Host "[$n/6] $text" -ForegroundColor Cyan }
function Ok($text)   { Write-Host "    OK  $text" -ForegroundColor Green }
function Warn($text) { Write-Host "    !   $text" -ForegroundColor Yellow }
function Gray($text) { Write-Host "  $text" -ForegroundColor DarkGray }
function Die($text)  { throw "Coda installer: $text" }   # throw, not exit: exit would close the window under 'irm | iex'

function Ask($question, $default) {
    if ($Yes) { return $default }
    $a = Read-Host "  $question [$default]"
    if ([string]::IsNullOrWhiteSpace($a)) { return $default } else { return $a.Trim() }
}

function Refresh-Path {
    $machine = [Environment]::GetEnvironmentVariable('Path', 'Machine')
    $user    = [Environment]::GetEnvironmentVariable('Path', 'User')
    $env:Path = "$machine;$user"
}

# A Python that is 3.10 or newer and has Tk (needed for the windows).
function Test-Python($exe, $extra) {
    try {
        $out = & $exe @extra -c "import sys, tkinter; print(sys.executable if sys.version_info >= (3, 10) else '')" 2>$null
        if ($LASTEXITCODE -eq 0 -and $out -and (Test-Path ($out | Select-Object -Last 1))) {
            return ($out | Select-Object -Last 1).Trim()
        }
    } catch { }
    return $null
}

function Find-Python {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        foreach ($v in @('-3.13', '-3.12', '-3.11', '-3.10', '-3')) {
            $p = Test-Python 'py' @($v)
            if ($p) { return $p }
        }
    }
    foreach ($name in @('python', 'python3')) {
        $cmd = Get-Command $name -ErrorAction SilentlyContinue
        # Skip the Microsoft Store placeholder, which only opens the Store.
        if ($cmd -and $cmd.Source -notlike '*\WindowsApps\*') {
            $p = Test-Python $cmd.Source @()
            if ($p) { return $p }
        }
    }
    foreach ($v in @('313', '312', '311', '310')) {
        $exe = Join-Path $env:LOCALAPPDATA "Programs\Python\Python$v\python.exe"
        if (Test-Path $exe) { $p = Test-Python $exe @(); if ($p) { return $p } }
    }
    return $null
}

Write-Host ''
Write-Host '   CODA' -ForegroundColor Blue
Write-Host '   Right-click any folder -> your AI coding agent opens there'

# Stop a running Coda first (it is started again at the end).
$running = Get-CimInstance Win32_Process |
    Where-Object { $_.CommandLine -match 'coda-(tray|preferences)\.py' }
if ($running) {
    $running | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
    Gray 'Stopped the running Coda - it restarts at the end.'
}

# -- 1: Python ---------------------------------------------------
Step 1 'Python'
$Py = Find-Python
if (-not $Py) {
    if (Get-Command winget -ErrorAction SilentlyContinue) {
        Gray 'Python not found - installing Python 3.12 for your user with winget...'
        winget install -e --id Python.Python.3.12 --scope user --silent `
            --accept-package-agreements --accept-source-agreements | Out-Host
        Refresh-Path
        $Py = Find-Python
    }
    if (-not $Py) {
        Die 'Python 3.10 or newer is needed. Install it from https://www.python.org/downloads/ (keep "tcl/tk" ticked), then run this again.'
    }
}
Ok $Py

# -- 2: Coda app -------------------------------------------------
Step 2 'Coda app'
$Here = $PSScriptRoot
if ($Here -and (Test-Path (Join-Path $Here 'coda.py')) -and (Test-Path (Join-Path $Here '.git'))) {
    $CodeDir = $Here
    Ok "using your git checkout at $CodeDir"
} else {
    $tmp = Join-Path ([IO.Path]::GetTempPath()) ('coda-install-' + [guid]::NewGuid())
    New-Item -ItemType Directory -Path $tmp | Out-Null
    try {
        if ($Here -and (Test-Path (Join-Path $Here 'coda.py'))) {
            $src = $Here                                 # e.g. unpacked from the skill zip
        } else {
            $zip = Join-Path $tmp 'coda.zip'
            Invoke-WebRequest -UseBasicParsing -Uri "https://github.com/$Repo/archive/refs/heads/$Branch.zip" -OutFile $zip
            Expand-Archive -Path $zip -DestinationPath $tmp
            $src = (Get-ChildItem -Path $tmp -Directory | Select-Object -First 1).FullName
        }
        if (-not (Test-Path (Join-Path $src 'coda.py'))) { Die 'the download does not look like Coda' }
        New-Item -ItemType Directory -Force -Path $DataDir | Out-Null
        if (Test-Path $AppDir) { Remove-Item -Recurse -Force $AppDir }
        Copy-Item -Recurse -Path $src -Destination $AppDir
    } finally {
        Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
    }
    $CodeDir = $AppDir
    Ok $CodeDir
}

# -- 3: Python environment ----------------------------------------
Step 3 'Python environment'
if (-not (Test-Path $VPy)) {
    & $Py -m venv $Venv
    if ($LASTEXITCODE -ne 0) { Die "could not create a Python environment in $Venv" }
}
& $VPy -m pip install -q --disable-pip-version-check --upgrade pip
& $VPy -m pip install -q --disable-pip-version-check pystray pillow
if ($LASTEXITCODE -ne 0) { Die 'could not install pystray and pillow' }
Ok $Venv

function Coda-Py($code) {
    & $VPy -c "import sys; sys.path.insert(0, r'$CodeDir'); import coda_common as C; $code"
}

# -- 4: Coding agent ----------------------------------------------
Step 4 'Coding agent for right-click -> Call Coda'
if (-not $Engine -and (Test-Path (Join-Path $env:APPDATA 'Coda\config.json'))) {
    $Engine = Coda-Py "print(C.load_config().get('engine', ''))"
}
if (-not $Engine) {
    $found = (Coda-Py "print(' '.join(e for e in C.installed_engines() if e != 'aider'))")
    $default = if ($found) { ($found -split ' ')[0] } else { 'claude' }
    if ($found) { Gray "Found on this computer: $found" }
    Write-Host '    claude        Claude Code'
    Write-Host '    codex         Codex CLI'
    Write-Host '    cursor-agent  Cursor Agent'
    Write-Host '    gemini        Gemini CLI'
    Write-Host '    aider         Aider - works with local Ollama models or an API key'
    $Engine = Ask 'Which agent should open' $default
}
$Engine = $Engine.ToLower()
if ($Engines -notcontains $Engine) { Die "unknown agent '$Engine' (choose from: $($Engines -join ', '))" }

if ($Engine -eq 'aider') {
    $aiderExe = Join-Path $DataDir 'aider-env\Scripts\aider.exe'
    if (Test-Path $aiderExe) {
        Ok "aider already installed"
    } else {
        # aider supports Python 3.10 - 3.12
        $aPy = $null
        if (Get-Command py -ErrorAction SilentlyContinue) {
            foreach ($v in @('-3.12', '-3.11', '-3.10')) { $aPy = Test-Python 'py' @($v); if ($aPy) { break } }
        }
        if (-not $aPy) {
            Warn 'aider needs Python 3.10 - 3.12; install one and run this again, or pick another agent later in Preferences'
        } else {
            Gray 'Installing aider - this takes a few minutes...'
            & $aPy -m venv (Join-Path $DataDir 'aider-env')
            & (Join-Path $DataDir 'aider-env\Scripts\python.exe') -m pip install -q --disable-pip-version-check --prefer-binary aider-chat
            if ($LASTEXITCODE -eq 0) { Ok 'aider installed' } else { Warn 'aider could not be installed' }
        }
    }
} else {
    $exe = Coda-Py "print(C.find_engine('$Engine') or '')"
    if (-not $exe) { Warn "$Engine is not installed yet - install it, or pick another agent later in Preferences" }
}
Ok "Call Coda opens: $Engine"

# -- 5: Settings --------------------------------------------------
Step 5 'Settings'
Coda-Py "c = C.load_config(); c['engine'] = '$Engine'; C.save_config(c)"
Ok "saved to $(Join-Path $env:APPDATA 'Coda\config.json')"

# -- 6: Right-click menu, Start menu, start on login ---------------
Step 6 'Right-click menu, Start menu and start on login'
$integrate = @((Join-Path $CodeDir 'coda.py'), 'integrate')
if ($Yes) { $integrate += '--yes' }
if ($NoAutostart) { $integrate += '--no-autostart' }
& $VPy @integrate
if ($LASTEXITCODE -ne 0) { Die 'setting up the right-click menu failed' }
Refresh-Path

Write-Host ''
Write-Host "  Coda is installed." -ForegroundColor Green
Write-Host ''
Write-Host '    Right-click    any folder -> Call Coda'
Write-Host '                   (Windows 11: right-click -> Show more options -> Call Coda)'
Write-Host '    Tray icon      the C next to the clock; search "Coda" in the Start menu'
Write-Host '    Terminal       cd my-project; coda   (in a new terminal window)'
Write-Host '    Uninstall      coda uninstall   (or Preferences -> General)'
Write-Host ''
Write-Host '  Coda is a tool: you are responsible for how you use it. It comes with no'
Write-Host '  warranty and collects no data.'
Write-Host "    Terms     https://github.com/$Repo/blob/main/TERMS.md"
Write-Host "    Privacy   https://github.com/$Repo/blob/main/PRIVACY.md"
Write-Host ''
if (-not $NoStart) {
    Start-Process -FilePath $VPyw -ArgumentList "`"$(Join-Path $CodeDir 'coda-tray.py')`""
    Ok 'Coda is running - look for the C icon next to the clock'
}
