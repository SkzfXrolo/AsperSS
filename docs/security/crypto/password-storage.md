# Password Storage Comparison

## Argon2id
- mejor opción moderna.
- resistente a GPU (memory-hard).

## bcrypt
- ampliamente soportado.
- límite de longitud de input.

## scrypt
- memory-hard, menos estándar operativo hoy.

Recomendación Argus: Argon2id; fallback bcrypt si compatibilidad.
