$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$Workspace = Split-Path -Parent $Repo
$Python = Join-Path $Workspace '.venv\Scripts\python.exe'
$Results = Join-Path $Repo 'results'
$PidFile = Join-Path $Results 'overnight.pid'
$StopFile = Join-Path $Repo 'STOP'
$Script = Join-Path $Repo 'fast_leads.py'

if (-not (Test-Path -LiteralPath $Python)) {
    throw "Python nerastas: $Python"
}
if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = 0
    [void][int]::TryParse((Get-Content -LiteralPath $PidFile -Raw), [ref]$ExistingPid)
    if ($ExistingPid -gt 0 -and (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue)) {
        throw "Rinkimas jau paleistas (PID $ExistingPid)."
    }
    Remove-Item -LiteralPath $PidFile -Force
}

New-Item -ItemType Directory -Path $Results -Force | Out-Null
if (Test-Path -LiteralPath $StopFile) {
    Remove-Item -LiteralPath $StopFile -Force
}
foreach ($LogName in @('overnight.out.log', 'overnight.err.log')) {
    $LogPath = Join-Path $Results $LogName
    if (Test-Path -LiteralPath $LogPath) {
        Remove-Item -LiteralPath $LogPath -Force
    }
}

$Process = Start-Process -FilePath $Python `
    -ArgumentList @("`"$Script`"", '--overnight') `
    -WorkingDirectory $Repo `
    -RedirectStandardOutput (Join-Path $Results 'overnight.out.log') `
    -RedirectStandardError (Join-Path $Results 'overnight.err.log') `
    -WindowStyle Hidden `
    -PassThru

$Process.Id | Set-Content -LiteralPath $PidFile -Encoding ascii
Write-Output "Pilnas rinkimas paleistas fone. PID: $($Process.Id)"
Write-Output "Progresas ir kontaktai saugomi repo kataloge; sustabdymui paleisk stop_overnight.ps1."
