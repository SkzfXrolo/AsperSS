# Proceso de release

## 1) Preparar cambios

- Validar CI workflows principales.
- Actualizar changelog con `scripts/build/gen-changelog.sh`.
- Confirmar versionado del componente objetivo.

## 2) Tag y publicacion

- Plugin: crear tag `plugin-vX.Y.Z` para disparar release automatica.
- Android/Linux: publicar artifacts de CI y consolidar release notes.

## 3) Verificacion post-release

- Descargar artefactos y validar checksum.
- Confirmar enlaces de descarga.
- Monitorear incidencias de adopcion inicial.

## Rollback

- Mantener ultimo release estable disponible.
- Documentar causa y acciones correctivas.
