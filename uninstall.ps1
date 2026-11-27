# ===============================================================
#  Coda uninstaller for Windows - for when `coda uninstall` is not
#  available (a broken or half-removed install).
#
#    irm https://raw.githubusercontent.com/sebamuhr/Coda/main/uninstall.ps1 | iex
#
#  It runs Coda's own uninstaller from a temporary copy, so it can also
#  remove the app folder itself.
# ===============================================================
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$Repo   = 'sebamuhr/Coda'
$Branch = if ($env:CODA_BRANCH) { $env:CODA_BRANCH } else { 'main' }
$Files  = @('coda.py', 'coda_common.py', 'coda_windows.py')

# Any Python 3 outside Coda's own folder will do.
$Py = $null
if (Get-Command py -ErrorAction SilentlyContinue) {
    try { $out = & py -3 -c "import sys; print(sys.executable)" 2>$null; if ($out) { $Py = "$out".Trim() } } catch { }
}
if (-not $Py) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd -and $cmd.Source -notlike '*\WindowsApps\*') { $Py = $cmd.Source }
}
if (-not $Py) { throw 'Coda uninstaller: Python 3 is needed to run the uninstaller.' }

$tmp = Join-Path ([IO.Path]::GetTempPath()) ('coda-uninstall-' + [guid]::NewGuid())
New-Item -ItemType Directory -Path $tmp | Out-Null
try {
    foreach ($f in $Files) {
        $local = if ($PSScriptRoot) { Join-Path $PSScriptRoot $f } else { '' }
        if ($local -and (Test-Path $local)) {
            Copy-Item $local $tmp
        } else {
            Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/$Repo/$Branch/$f" `
                -OutFile (Join-Path $tmp $f)
        }
    }
    & $Py (Join-Path $tmp 'coda.py') uninstall @args
} finally {
    Remove-Item -Recurse -Force $tmp -ErrorAction SilentlyContinue
}
