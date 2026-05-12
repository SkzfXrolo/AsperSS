# Growth forecasting (Pack 48-H Round 6 · #161)

## Inputs

- Tasa rows/día por tabla.
- Bytes promedio por row.
- Crecimiento clientes esperados.

## Métodos

| Método | Pros |
| --- | --- |
| Lineal | simple, base |
| Exponencial | acepta growth % MoM |
| Cohort-based | precisión |
| Monte Carlo | rango con incertidumbre |

## Argus

Script Python existente: `scripts/db/cost-projection.py`. Re-correr trimestralmente con datos actualizados.

## Alertas

- Cuando proyectado 90d > 80% tier actual → planificar upgrade.

## Referencias

- `docs/db/cost-forecast.md`
