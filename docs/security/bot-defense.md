# Bot Defense Design

## Cloudflare controls

- habilitar Bot Fight Mode,
- challenge para patrones sospechosos (JA3/ASN/rate),
- managed challenge en `/login`, `/register`, `/api/auth/*`.

## reCAPTCHA v3 integration (diseño)

- aplicar score en login/registro,
- umbral inicial sugerido: `0.5`,
- acciones low-score: challenge adicional o cooldown.

## Endpoint hardening

- rate limit por IP + por usuario + por ruta,
- device fingerprint ligero para abuso repetitivo,
- bloqueo temporal progresivo ante fallos de auth.
