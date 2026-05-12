# Argus Projects — Schema migration tools comparison (Pack 48-H Round 2)

## Criterios de evaluación

| Criterio | Peso |
| --- | --- |
| Ajuste al ecosistema Python / Flask | Alto |
| Idempotencia y orden estricto | Alto |
| Reviewabilidad (diff SQL en PR) | Alto |
| Soporte PG + SQLite (dual-mode) | Medio |
| Curva de aprendizaje equipo | Medio |

## Comparativa

| Herramienta | Pros | Contras | PG + SQLite |
| --- | --- | --- | --- |
| **Alembic** | Nativo SQLAlchemy; revisiones Python o SQL; branching; autogenerate opcional | Requiere modelo SA o SQL manual disciplinado | Un `env.py` por dialecto o branches separados |
| **Flyway** | SQL versionado `V1__x.sql`; agnóstico de lenguaje | Menos integrado con Flask; licencia Teams | Soporta múltiples URLs con profiles |
| **Sqitch** | Deploy/revert/verify explícitos; excelente para equipos DBA puros | Curva más alta; menos adopción Python | Sí |
| **Raw SQL + scripts** | Cero deps; ya es el estado actual (DDL en Python) | Caos a escala; sin orden garantizado | Ya sufrido |

## Recomendación: **Alembic**

1. El proyecto ya es Python-first; Alembic encaja en CI (`alembic upgrade head`).
2. Permite **baseline** desde el estado actual sin reescribir historia (`stamp head`).
3. Migraciones futuras (F-001 `scans.company_id`) como `revision` revisable en PR.

## Anti-patrones a evitar

- Mezclar `alembic revision --autogenerate` sin revisión humana (borra índices fantasma).
- Correr `upgrade` en el mismo proceso que sirve HTTP sin lock (usar job Render pre-deploy).

## Próximo paso

Ver `scripts/db/alembic-bootstrap.md` para inicialización.
