# Distributed Tracing with OpenTelemetry (Pack48-G)

## Objetivo

Seguir una request end-to-end entre frontend, API, DB y servicios auxiliares.

## Diseño propuesto

- Instrumentar Flask con OpenTelemetry SDK.
- Exportar traces a Datadog/Sentry/OTLP collector.
- Propagar `traceparent` en headers entre servicios.

## Span model sugerido

- `http.request`
- `db.query`
- `ai.evaluate`
- `plugin.http.call`
- `scanner.submit`

## Sampling

- Base: 5-10%.
- Errores: 100%.
- Incrementar sampling en incidentes temporales.

## KPIs

- Reducción de MTTR.
- Identificación de bottleneck dominante por ruta.
