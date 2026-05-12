# SIEM Integration for Argus

Comparativa resumida:

- Wazuh: OSS, costo bajo, all-in-one.
- Splunk: potente, costo alto.
- ELK: flexible, requiere operación.
- Sentinel: cloud-native Microsoft.

Recomendación Argus: **Wazuh**.

## Setup base

1. agentes en web, DB, workers y endpoints críticos.
2. manager central + indexador.
3. dashboards de auth, API abuse y exfil.
4. integración con alerting (email/chat/on-call).
