# Anti-patterns de testing

- Tests que dependen del orden global.
- Tests que dependen de internet sin control.
- Tests que dependen de hora local.
- Assertions vagas (`assert x` sin contexto).
- Snapshot gigantes difíciles de revisar.
- Fixtures con estado mutable compartido.
- Retries silenciosos que esconden flaky.
- Ignorar fallos reales como "intermitentes" sin ticket.
- Acoplar tests a detalles internos frágiles.
- No versionar baseline de performance.
