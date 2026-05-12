# Cost-Aware Engineering (Pack48-G)

## Objetivo

Optimizar rendimiento sin perder de vista costo operativo.

## Métricas clave

- costo por oracle eval
- costo por scan procesado
- costo por 1k requests API

## Patrones

- autoscaling prudente
- capacidad reservada donde aplique
- right-sizing por servicio

## Render enfoque práctico

- evitar workers ociosos permanentes.
- mover tareas batch fuera de web workers.
- cachear para bajar CPU/DB time.

## Alertas de costo

- detectar anomalías diarias/semanales.
- correlacionar picos de costo con features/tenants.
