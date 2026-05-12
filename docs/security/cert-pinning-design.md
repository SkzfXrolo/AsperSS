# Certificate Pinning Design (Scanner + Plugin)

## Objetivo

Reducir riesgo MITM incluso con CA comprometida, aplicando pinning por SPKI.

## Formato de pin

- tipo: `SPKI SHA-256`
- encoding: `base64`
- ejemplo:
  - `sha256/AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA=`

## Estrategia de rotación

Usar doble pin:

- `current_pin`
- `next_pin`

Proceso:

1. desplegar backend con cert cuya key pública coincide con `current`.
2. distribuir clientes con `current + next`.
3. rotar backend a cert `next`.
4. distribuir nuevo `next2`.

## Scanner Python (`requests`)

## Diseño

- custom `HTTPAdapter` con validación post-handshake de SPKI pin.
- validar pin en cada conexión TLS.
- rechazar conexión si pin no coincide con `current` o `next`.

## Modo desarrollo

- env var `ARGUS_DEV_INSECURE=1` desactiva pinning (solo dev/local).
- registrar warning claro en logs.

## Plugin Java

## Diseño

- `SSLContext` con `X509TrustManager` custom:
  - primero validación PKIX estándar
  - luego extracción SPKI de cert leaf
  - comparar hash SHA-256(base64) con pinset

Si no coincide:

- abortar request TLS con excepción.

## Android (alineado)

- preferir `network_security_config` con pin-set y expiración.
- mantener doble pin igual que scanner/plugin.

## Gestión operativa de pins

- almacenar en config segura (env/secrets manager), no hardcode en repositorios públicos.
- versionar pinset con metadata:
  - `pin_id`
  - `valid_from`
  - `valid_to`
  - `owner`

## Failure policy

- `hard-fail` en producción.
- `soft-fail` temporal sólo durante migraciones controladas y con telemetría.

## Checklist implementación

1. tests unitarios de cálculo SPKI hash,
2. test de handshake contra cert válido/inválido,
3. feature flag de emergencia para rollback controlado,
4. runbook de rotación trimestral.
