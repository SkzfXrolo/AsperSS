# Encryption Spec (AES-256-GCM)

- cifrado autenticado: AES-256-GCM.
- IV único por clave (96 bits recomendado).
- prohibido reutilizar IV.
- almacenar `ciphertext + iv + tag`.
- claves en KMS/secret manager.
- rotación periódica y por incidente.
