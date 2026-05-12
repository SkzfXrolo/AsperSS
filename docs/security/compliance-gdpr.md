# Compliance Check GDPR/LGPD — Pack48 Round 2

## Disclaimer

Este documento es técnico-operativo y **no reemplaza asesoría legal**.

## ¿Aplica GDPR/LGPD?

Probablemente **sí**, porque Argus procesa datos que pueden identificar o perfilar personas:

- IP pública,
- UUID/username de jugador,
- machine identifiers,
- historial de conducta (verdicts/flags),
- potencial metadata de chat/comandos.

## Base legal del tratamiento (orientativa)

- **Interés legítimo** (seguridad/anti-cheat y prevención de fraude).
- **Ejecución contractual** con servidores/comunidades que usan el servicio.
- Si se usan analíticas no esenciales, evaluar consentimiento explícito.

## Derechos del titular (estado actual)

## Derecho de acceso

- No se observó endpoint público/documentado para exportación completa de datos por usuario final.
- Recomendación: endpoint/flujo de "export my data".

## Derecho al olvido

- [NEW][HIGH] no se evidencia flujo formal de borrado por sujeto de datos.
- Recomendación: proceso operativo + endpoint administrativo auditado para borrar/anonimizar por identificador.

## Rectificación / limitación / oposición

- No hay evidencia de procedimiento documentado completo en docs públicas.

## Retención y minimización

- [NEW][HIGH] no hay política de retención formal para `scans`, `ai_decisions_log`, `ai_feedback` y logs operativos.
- Recomendación: política por tabla (TTL), purge jobs y registros de ejecución.

## Cookies y panel web

- Si solo se usan cookies estrictamente necesarias de sesión, banner puede no ser obligatorio en muchas jurisdicciones.
- Si se agregan cookies de tracking/analytics, sí requerirá consentimiento/banner.

## Privacy Policy

- [NEW][MEDIUM] no se detectó una política de privacidad técnica central en el set auditado de seguridad.
- Recomendación: publicar/ligar política desde sitio y panel.

## Checklist mínimo de compliance recomendado

1. inventario de datos personales por flujo,
2. ROPA (registro de actividades de tratamiento),
3. base legal documentada por finalidad,
4. DPA con subprocesadores (infra/AI),
5. flujo de DSAR (acceso, borrado, rectificación),
6. política de retención y minimización.
