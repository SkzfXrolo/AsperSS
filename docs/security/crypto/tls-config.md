# TLS Configuration Baseline

- TLS 1.3 obligatorio (TLS 1.2 solo compatibilidad controlada).
- suites modernas (AEAD + PFS).
- HSTS (`max-age` >= 6 meses, includeSubDomains).
- OCSP stapling habilitado.
- deshabilitar weak ciphers y renegotiation insegura.
