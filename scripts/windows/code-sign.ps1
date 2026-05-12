param(
  [string]$FilePath = "dist\\ArgusScanner.exe",
  [string]$CertThumbprint = "TBD",
  [string]$TimestampUrl = "http://timestamp.digicert.com"
)

$ErrorActionPreference = "Stop"
signtool sign /fd SHA256 /tr $TimestampUrl /td SHA256 /sha1 $CertThumbprint $FilePath
Write-Host "Firma aplicada a $FilePath"
