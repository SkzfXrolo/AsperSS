# Cost Attribution by Feature

Objetivo: identificar features más caras por request.

Metodología:
1. medir CPU/DB/network por endpoint,
2. mapear endpoint -> feature,
3. convertir consumo a costo unitario.

Salida:
- top 10 features por costo total,
- top 10 por costo por operación.
