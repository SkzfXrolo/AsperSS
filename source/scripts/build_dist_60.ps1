# Build ArgusScanner.exe - real payload only, no PE padding
Set-Location $PSScriptRoot\..

python scripts\prepare_bundle.py
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

python -m PyInstaller ArgusScanner.spec --noconfirm --distpath dist_60 --workpath build_60
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$exe = Get-Item "dist_60\ArgusScanner.exe"
$mb = [math]::Round($exe.Length / 1MB, 2)
Write-Host "OK: $mb MiB ($($exe.Length) bytes) - sin padding"
if ($exe.Length -lt 55MB) {
    Write-Host "AVISO: menor que 55 MiB; solo peso util embebido."
}
Copy-Item $exe.FullName "dist_new3\ArgusScanner.exe" -Force
Write-Host "Copiado a dist_new3"
