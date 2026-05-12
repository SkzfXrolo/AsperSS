# Model Registry (Deep)

## Comparativa: MLflow vs W&B vs ClearML vs Neptune

| Feature | MLflow | Weights & Biases | ClearML | Neptune |
|---|---|---|---|---|
| Open source core | Si | No | Si | No |
| Model registry nativo | Si | Si | Si | Si (metadata-driven) |
| Experiment tracking | Si | Excelente | Excelente | Excelente |
| Artifact store | S3/GCS/Azure | Integrado | Integrado | Integrado |
| Governance workflows | Medio | Alto | Alto | Alto |
| On-prem | Si | Limitado/enterprise | Si | Enterprise |
| Integracion notebooks | Alta | Muy alta | Alta | Muy alta |
| UI comparacion runs | Buena | Muy buena | Muy buena | Muy buena |
| Escalado enterprise | Medio/alto | Alto | Alto | Alto |
| Costo inicial | Bajo | Medio/alto | Medio | Medio/alto |
| Vendor lock-in | Bajo | Medio | Medio | Medio |
| Setup time | Bajo | Bajo | Medio | Bajo |

## Recomendacion Argus

- **Base OSS/control:** MLflow.
- **Colaboracion y UX fuerte de data science:** W&B.
- **Orquestacion MLOps completa on-prem:** ClearML.
- **Tracking de experimentos en equipos distribuidos:** Neptune.

## Criterios de decision

- Requisitos de compliance y retencion.
- Necesidad de on-prem real.
- Coste por usuario/equipo y por storage.
- Integracion con pipeline de despliegue existente.
