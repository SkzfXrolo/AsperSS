# Secure Coding Python (Argus)

## Top 10 prácticas

1. usar queries parametrizadas siempre (`cursor.execute(sql, params)`).
2. nunca interpolar input de usuario en SQL dinámico sin allowlist.
3. validar/normalizar entrada por esquema (tipos, longitudes, formatos).
4. escapar salida HTML/JS (evitar `innerHTML` sin sanitización).
5. no loguear secretos (`token`, `api_key`, `password`, `cookie`).
6. usar `secrets` para tokens aleatorios criptográficos.
7. comparar secretos con `hmac.compare_digest`.
8. aplicar rate-limit y límites de payload en endpoints públicos.
9. definir timeouts en requests salientes.
10. manejar errores sin filtrar internals en respuestas.

## Checklist rápido PR

- [ ] ¿hay input user-controlled?
- [ ] ¿hay validación server-side?
- [ ] ¿hay riesgo de inyección/XSS?
- [ ] ¿se filtran secretos en logs/respuestas?
- [ ] ¿hay tests de seguridad para el cambio?
