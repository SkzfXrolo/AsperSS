# Runbook de firma y notarizacion macOS

## Prerrequisitos

- Certificado Developer ID Application en keychain.
- Credenciales de notarizacion Apple (`APPLE_ID`, `APPLE_TEAM_ID`, app password).
- Runner `macos-latest`.

## Flujo CI

1. Build `.app` con PyInstaller.
2. Empaquetar `.dmg` con `create-dmg`.
3. Firmar app y dmg con `codesign`.
4. Enviar a notarizacion con `xcrun notarytool submit --wait`.
5. Ejecutar `stapler` para ticket local.
6. Publicar artefactos firmados.

## Variables de secreto (REVIEW)

- `MACOS_DEVELOPER_ID_APP`
- `MACOS_APPLE_ID`
- `MACOS_APPLE_TEAM_ID`
- `MACOS_APP_PASSWORD`
