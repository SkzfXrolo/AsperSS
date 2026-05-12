# FALSE POSITIVES

- `Run/RunOnce` en `%APPDATA%` puede ser software legitimo per-user.
- Hosts entries corporativas pueden verse como overrides public DNS.
- Reglas firewall "allow" en herramientas de administracion remota legitima.
- DLLs junto a EXE en software portable no siempre implican sideloading.
- Historiales de browser con dominios raros pueden ser telemetria/CDN.

## Whitelist sugerida

- Por hash (`sha256`) de binarios firmados/validados.
- Por publisher (firma digital valida y esperada).
- Por ruta confiable conocida en entorno del cliente.

