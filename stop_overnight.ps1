$ErrorActionPreference = 'Stop'

$Repo = Split-Path -Parent $MyInvocation.MyCommand.Path
$Results = Join-Path $Repo 'results'
$PidFile = Join-Path $Results 'overnight.pid'
$StopFile = Join-Path $Repo 'STOP'

New-Item -ItemType File -Path $StopFile -Force | Out-Null
if (Test-Path -LiteralPath $PidFile) {
    $ExistingPid = 0
    [void][int]::TryParse((Get-Content -LiteralPath $PidFile -Raw), [ref]$ExistingPid)
    if ($ExistingPid -gt 0 -and (Get-Process -Id $ExistingPid -ErrorAction SilentlyContinue)) {
        Write-Output "Sustabdymas paprašytas. Programa užbaigs šiuo metu pradėtą paiešką ir išsaugos progresą (PID $ExistingPid)."
        exit 0
    }
    Remove-Item -LiteralPath $PidFile -Force
}
Write-Output 'Aktyvaus rinkimo proceso nerasta. STOP žymė palikta, kad naujas procesas neprasidėtų netyčia.'
