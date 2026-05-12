# Capacity Model

Modelo simple:

`costo_total = usuarios * scans_por_dia * costo_por_scan * días`

Extensión:
- sumar costo por oracle eval y almacenamiento.
- incluir crecimiento mensual compuesto.

Análisis de sensibilidad:
- 10x usuarios,
- 100x usuarios,
- identificar primer cuello (CPU, DB, red, colas).
