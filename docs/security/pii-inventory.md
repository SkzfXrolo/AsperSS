# PII Inventory — Argus

## Tabla de inventario

| Campo | Fuente | Sensibilidad | Base legal (GDPR) | Uso | Retención propuesta |
|---|---|---:|---|---|---|
| username | panel/plugin/scanner | Media | Interés legítimo | identificación staff/jugador | 365d (anonimizable) |
| email staff | auth web | Alta | Contrato / interés legítimo | login/comunicación | mientras cuenta activa |
| IP address | scanner/web/plugin logs | Alta | Interés legítimo | seguridad/fraude | 90d |
| machine_id | scanner | Alta | Interés legítimo | correlación de scans | 180d |
| machine_name | scanner | Media | Interés legítimo | contexto operativo | 90d |
| minecraft_uuid | plugin/scanner | Media | Interés legítimo | correlación anti-cheat | 365d |
| minecraft_username | plugin/scanner | Media | Interés legítimo | operaciones staff | 365d |
| country | geolookup scanner | Baja/Media | Interés legítimo | detección de riesgo | 90d |
| verdict_reason | staff/AI | Media/Alta | Interés legítimo | auditoría decisiones | 365d |
| ai_decision_log | backend IA | Media/Alta | Interés legítimo | explicabilidad y calidad | 180d |
| plugin_key metadata | panel admin | Alta | Interés legítimo | autenticación M2M | hasta revocación + 365d audit |
| scan_token metadata | scanner/web | Alta | Interés legítimo | autorización escaneo | TTL + 90d audit |
| chat/command security events | plugin | Media | Interés legítimo | detección spam/abuso | 90d |
| ban history | panel/plugin | Alta | Interés legítimo | seguridad de comunidad | permanente con anonimización parcial post-1y |

## Notas

- Este inventario debe mapearse a ROPA y DPA con proveedores externos.
- Datos de menores pueden requerir controles adicionales según jurisdicción.
