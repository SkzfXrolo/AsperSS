# Bug Bounty Scope (Propuesta)

## In-scope assets

- `https://asperss.onrender.com`
- API `web_app`
- Plugin ArgusMC
- Scanner desktop/linux
- Cliente Android

## Out-of-scope

- social engineering/phishing a staff real
- ataques físicos
- DoS volumétrico
- reportes sin impacto de seguridad real

## Severity -> bounty table (ejemplo)

| Severidad | Ejemplos | Rango bounty (USD) |
|---|---|---:|
| Critical | RCE, auth bypass admin, exfil masiva | 1500-5000 |
| High | IDOR sensible, SSRF crítica, token compromise | 600-1500 |
| Medium | XSS stored acotado, info leak relevante | 200-600 |
| Low | hardening gaps con impacto bajo | 50-200 |

## Safe harbor

Investigación de buena fe está permitida si:

- no exfiltras datos innecesarios,
- no alteras/disrumpes servicio de forma destructiva,
- reportas de forma privada y responsable.

## Contacto de seguridad

- `security@argusprojects.com` (TBD)

## `security.txt` proposal

Archivo propuesto (fuera de scope de este worker para crear en `web_app/static/.well-known/security.txt`):

```text
Contact: mailto:security@argusprojects.com
Policy: https://asperss.onrender.com/security
Preferred-Languages: es, en
Expires: 2027-12-31T23:59:59.000Z
```
