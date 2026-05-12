# Guia de integracion para servidores grandes

## 1) Testear sin enforcement (observer mode)

- Activar `observerMode: true`.
- Mantener `enforcement.enabled: false`.
- Registrar alertas durante 3-7 dias en horarios pico.
- Etiquetar falsos positivos por tipo de check.

## 2) Activacion gradual de enforcement

1. Fase 1: solo warnings internos al staff.
2. Fase 2: kicks para violaciones altas y repetidas.
3. Fase 3: sanciones completas con umbral conservador.
4. Fase 4: ajuste fino por modalidad (PvP, minijuegos, survival).

## 3) Tuning de thresholds

- Subir threshold en checks con jitter de red alto.
- Bajar threshold solo donde haya evidencia estable.
- Separar perfiles por tipo de servidor si aplica.
- Revisar semanalmente top alertas por volumen y precision.

## Sugerencia operativa

Usar ventanas de observacion cortas para cambios grandes y siempre desplegar en low-risk nodes antes de ir a toda la red.
