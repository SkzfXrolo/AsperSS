# HMAC-SHA256 Implementation Spec

Referencia: RFC 2104 y vectores RFC 4231.

## Canonical string

`METHOD\nPATH\nNONCE\nTIMESTAMP_MS\nBODY_SHA256_HEX`

## Verificación

1. validar ventana temporal.
2. verificar nonce único.
3. recalcular HMAC con clave activa.
4. comparar con `compare_digest`.

## Test vectors

- usar casos RFC 4231 (case 1/2/3) para regresión.
