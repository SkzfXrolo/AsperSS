# Tree storage patterns (Pack 48-H Round 6 · #157)

## Adjacency list

```text
id, parent_id
```

- Inserts O(1).
- Subtree queries → recursive CTE.

## Nested set (Celko)

```text
id, lft, rgt
```

- Subtree queries O(log n).
- Inserts O(n).

## Materialized path

```text
id, path TEXT (e.g. '/root/branch/leaf')
```

- Buen balance.
- Patterns con `LIKE 'root/%'`.

## `ltree` extension

- Tipo dedicado labels jerárquicos.
- Operadores `<@`, `@>`, GIN/GiST.

## Argus

Si surge necesidad (org tree staff, categorías ban): `ltree` + GIN si extension disponible.

## Referencias

- `docs/db/extensions-evaluation.md`
