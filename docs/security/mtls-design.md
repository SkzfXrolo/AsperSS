# mTLS Design (Service-to-Service)

## Objetivo

Autenticar ambos extremos en comunicaciones internas críticas:

- plugin <-> web API
- scanner backend <-> web API (si aplica)

## Diseño

- CA interna dedicada (self-signed o PKI gestionada),
- cert por servicio/entorno,
- validación mutua de cert en gateway (nginx/envoy).

## Implementación propuesta

- **Nginx:** `ssl_verify_client on;` + trust store CA interna.
- **Python requests:** `cert=(client.crt, client.key)` y `verify=ca.pem`.
- **Java:** `SSLContext` con keystore/truststore por servicio.

## Rotación

- certs de corta vida (90 días),
- overlap de certificados para zero-downtime,
- revocación rápida por incidente.

## Coste vs beneficio

- Beneficio alto: reduce spoofing lateral y robo de credenciales estáticas.
- Coste medio-alto: PKI lifecycle, distribución de certs, observabilidad TLS.
