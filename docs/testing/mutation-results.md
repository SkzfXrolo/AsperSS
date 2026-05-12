# Interpretación de mutation testing

- **Killed mutant**: bien, los tests detectaron cambio inválido.
- **Survived mutant**: gap de test, hay que reforzar casos.
- **Timeout/error**: revisar estabilidad del test runner.

Priorizar sobrevivientes en lógica de negocio crítica (`argus_ai_oracle`, `argus_ai_trainer`).
