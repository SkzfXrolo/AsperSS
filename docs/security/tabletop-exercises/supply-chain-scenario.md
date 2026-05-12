# Tabletop: Supply Chain Scenario

## Setup

- dependencia externa comprometida llega a pipeline.

## Inject timeline

- T+0: alerta de CVE crítica en dependencia usada.
- T+25: evidencia de artifact manipulado.
- T+50: release reciente podría estar afectado.

## Decisiones esperadas

- freeze de releases,
- rollback/recall de artifacts,
- validación de firma/checksums,
- comunicación a clientes y plan de parche.

## Lessons learned template

- cobertura de controles supply-chain,
- gaps de proceso,
- automatizaciones nuevas requeridas.
