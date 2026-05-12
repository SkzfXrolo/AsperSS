# Estrategia de promoción GitOps

- Branch `dev` -> auto deploy `dev`.
- Tag `staging-*` -> promoción a `staging`.
- Tag `v*` -> promoción a `prod` con aprobación manual.
- Rollback: revert commit/tag en Git.
