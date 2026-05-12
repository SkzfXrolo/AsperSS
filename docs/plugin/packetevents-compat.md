# Matriz de compatibilidad PacketEvents

| Argus Plugin | PacketEvents | Estado | Notas |
| --- | --- | --- | --- |
| 1.0.x | 2.6.x | Recomendado | Baseline objetivo para despliegue |
| 1.0.x | 2.5.x | Parcial | Revisar eventos edge-case |
| 1.0.x | 2.4.x o menor | No recomendado | Riesgo de API mismatch |

## Politica sugerida

1. Fijar version minima recomendada en docs de release.
2. Validar arranque y soft-dep fallback cuando PacketEvents no este.
3. Registrar warning claro al iniciar si la version no esta soportada.

## REVIEW

- Confirmar versiones exactas contra `pom.xml` del plugin.
