# AI Model Optimization (Pack48-G)

## Técnicas

1. Quantization (fp32 -> int8)
2. Pruning (remover pesos de bajo impacto)
3. Knowledge distillation (teacher -> student)
4. ONNX export para runtime optimizado

## Beneficios esperados

- Menor latencia inferencia.
- Menor memoria de modelo.
- Menor consumo energético por evaluación.

## Caching de predicciones

- Cachear entradas repetidas de corto plazo.
- Invalidar por versión de modelo y tenant.
