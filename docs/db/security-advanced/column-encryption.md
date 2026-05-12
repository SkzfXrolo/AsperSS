# Column-level encryption (Pack 48-H Round 5 · #146)

## Opciones

| Opción | Pros | Contras |
| --- | --- | --- |
| `pgcrypto` pgp_sym_encrypt | DB-side | key management difícil |
| App-level AES-GCM | rotación KMS simple | no protege dumps DB sin cifrado |
| Transparent Data Encryption | infra | proveedor |

## Patrón híbrido Argus

- PII alta (IP, chat) cifrada app + hash para lookup (`argus_hash_pii`).
- Columnas restantes en claro con clasificación `data-classification.md`.

## Rotación

- Versionar `ciphertext_version` column.
- Re-encrypt batch nocturno.

## Referencias

- `docs/db/encryption-strategy.md`
