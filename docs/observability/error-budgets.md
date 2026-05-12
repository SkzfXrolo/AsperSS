# Error Budgets Operational Playbook (Pack48-G)

## Base

Si SLO uptime mensual = 99.5%, el error budget mensual es ~0.5%.

## Burn-rate policy

- Burn-rate bajo: roadmap normal.
- Burn-rate medio: congelar features de riesgo.
- Burn-rate alto: solo fixes de confiabilidad/performance.

## Reglas prácticas

1. Si se consume >25% budget en 1 semana: revisión técnica obligatoria.
2. Si se consume >50% en media ventana: freeze parcial.
3. Si se consume >80%: freeze total no crítico hasta estabilizar.

## Inputs

- p99 latencia
- error rate
- disponibilidad probe

## Salidas

- estado semanal del budget
- acciones correctivas con owner y fecha
