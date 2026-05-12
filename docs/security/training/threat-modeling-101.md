# Threat Modeling 101 (rápido para features nuevas)

## Método de 20 minutos

1. dibujar flujo de datos (cliente -> API -> DB -> terceros).
2. listar activos críticos (secrets, PII, auth tokens).
3. aplicar STRIDE por componente.
4. priorizar 3 riesgos top por impacto x probabilidad.
5. definir mitigaciones antes de merge.

## Preguntas guía

- ¿quién podría abusar de esta feature?
- ¿qué datos sensibles toca?
- ¿qué pasa si se manipulan parámetros de entrada?
- ¿hay abuso por volumen/costo?
- ¿se puede romper aislamiento entre empresas/usuarios?

## Output mínimo esperado

- diagrama simple,
- tabla de amenazas,
- plan de mitigaciones y tests.
