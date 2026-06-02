# Firma digital del Argus Scanner (Windows)

Windows SmartScreen y Defender marcan como "sospechoso" a los `.exe` **sin firma Authenticode**. No hay atajo gratuito legítimo: hace falta un **certificado de firma de código** emitido por una CA de confianza.

## Opciones recomendadas

| Proveedor | Tipo | Notas |
|-----------|------|--------|
| [SSL.com](https://www.ssl.com/) | OV Code Signing | Económico, validación de organización |
| DigiCert / Sectigo | EV Code Signing | Menos avisos SmartScreen; requiere token USB (EV) |

Evitar certificados "self-signed" para distribución pública: no eliminan el warning de SmartScreen.

## Requisitos en la máquina de build

1. Windows 10/11 con **Windows SDK** (incluye `signtool.exe`).
2. Certificado instalado en el almacén **Personal** del usuario o en un token EV.
3. Variables de entorno (opcional):

```powershell
$env:ARGUS_SIGN_PFX = "C:\certs\aspers-code-sign.pfx"
$env:ARGUS_SIGN_PASSWORD = "tu-password-seguro"
$env:ARGUS_SIGN_TIMESTAMP = "http://timestamp.digicert.com"
```

## Firmar después de PyInstaller

Desde la raíz del repo:

```powershell
.\BAT\sign_scanner.ps1 -ExePath "source\dist_new3\ArgusScanner.exe"
```

El script usa `signtool sign` con SHA256 y sellado de tiempo.

## Reputación SmartScreen (sin certificado aún)

- Publicar siempre el **mismo** binario desde el mismo dominio (Render / GitHub Releases).
- Pedir a los staff que usen "Más información" → "Ejecutar de todas formas" la primera vez.
- Con certificado OV/EV, la reputación mejora en días/semanas según descargas.

## Integración en CI (futuro)

Guardar el `.pfx` como secreto cifrado en GitHub Actions y firmar en el job de release **antes** de subir el artefacto.
