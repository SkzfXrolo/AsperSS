# Runbook de code signing (Windows EV)

1. Proteger certificado EV en HSM/token.
2. Firmar binario y setup con `signtool`.
3. Aplicar timestamp authority.
4. Verificar firma en CI y SmartScreen reputation.
5. Publicar artefactos firmados.
