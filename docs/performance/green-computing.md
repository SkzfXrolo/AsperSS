# Green Computing (Pack48-G)

## Estimación de huella

- gCO2 por usuario = compute + transferencia + storage.
- Inputs: CPU time/request, bytes transferidos, GB-mes almacenados.
- Herramientas: WebsiteCarbon (web), Cloud Carbon Footprint (infra cloud).

## Optimizaciones

1. Dark mode (ahorro en OLED).
2. Lazy loading de JS/imágenes.
3. Inferencia ML eficiente (distillation + cache de predicciones).
4. Reducir polling y bytes en wire.

## Render / infraestructura

- Preferir regiones con mayor % de energía renovable cuando sea viable.
- Programar jobs batch fuera de picos para mejorar eficiencia energética.

## KPI sugeridos

- gCO2/request
- gCO2/scan
- gCO2/oracle-eval
