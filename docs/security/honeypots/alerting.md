# Canary Alerting

## Flujo de alertas

1. canary hit detectado,
2. webhook handler recibe evento,
3. envía alerta a Slack/email,
4. abre incidente con severidad inicial medium/high según contexto.

## Payload mínimo de evento

- token canary id,
- source IP/UA,
- timestamp UTC,
- endpoint/recurso tocado.

## Canales recomendados

- Slack `#security-incidents`
- email `security@argusprojects.com`
- opcional pager para hits repetidos.
