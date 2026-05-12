# WAF Deployment Guide

## NGINX + ModSecurity

1. instalar ModSecurity v3 + OWASP CRS.
2. incluir `scripts/security/waf/argus-modsec.conf`.
3. ajustar CRS con `scripts/security/waf/crs-config.yaml`.
4. arrancar en modo detection-only y pasar luego a block.

## Cloudflare WAF

- crear reglas equivalentes por ruta:
  - `/api/auth/login` rate-limit,
  - `/api/admin/*` geo/challenge,
  - bloqueos XSS/SQLi managed rules.

## AWS WAF

- asociar WebACL al ALB/CloudFront,
- definir rate-based rules y managed rule groups,
- configurar logging a S3/CloudWatch.
