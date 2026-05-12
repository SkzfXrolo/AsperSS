# Random Generation

- usar CSPRNG (`secrets`, `os.urandom`).
- no usar `random` para tokens/keys.
- longitud mínima: 128 bits de entropía para tokens.
- invalidar tokens tras uso.
- auditar generación en tests de seguridad.
