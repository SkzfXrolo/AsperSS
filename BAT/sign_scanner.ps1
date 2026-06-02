# Firma Authenticode del ArgusScanner.exe (requiere certificado PFX o cert en almacén).
param(
    [string]$ExePath = "source\dist_new3\ArgusScanner.exe",
    [string]$PfxPath = $env:ARGUS_SIGN_PFX,
    [string]$Password = $env:ARGUS_SIGN_PASSWORD,
    [string]$TimestampUrl = $(if ($env:ARGUS_SIGN_TIMESTAMP) { $env:ARGUS_SIGN_TIMESTAMP } else { "http://timestamp.digicert.com" })
)

$ErrorActionPreference = "Stop"
if (-not (Test-Path $ExePath)) {
    Write-Error "No existe: $ExePath"
}

$signtool = Get-Command signtool.exe -ErrorAction SilentlyContinue
if (-not $signtool) {
    $sdk = "${env:ProgramFiles(x86)}\Windows Kits\10\bin"
    if (Test-Path $sdk) {
        $latest = Get-ChildItem $sdk -Directory | Sort-Object Name -Descending | Select-Object -First 1
        $candidate = Join-Path $latest.FullName "x64\signtool.exe"
        if (Test-Path $candidate) { $signtool = $candidate }
    }
}
if (-not $signtool) {
    Write-Error "signtool.exe no encontrado. Instalá Windows SDK."
}

Write-Host "Firmando $ExePath ..."

if ($PfxPath -and (Test-Path $PfxPath)) {
    if (-not $Password) {
        $sec = Read-Host "Password del PFX" -AsSecureString
        $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
        $Password = [Runtime.InteropServices.Marshal]::PtrToStringAuto($ptr)
    }
    & $signtool sign /fd SHA256 /tr $TimestampUrl /td SHA256 /f $PfxPath /p $Password $ExePath
} else {
    # Certificado ya en almacén (EV token): usar /a para auto-selección
    & $signtool sign /fd SHA256 /tr $TimestampUrl /td SHA256 /a $ExePath
}

& $signtool verify /pa $ExePath
Write-Host "OK — verificar con: Get-AuthenticodeSignature '$ExePath'"
