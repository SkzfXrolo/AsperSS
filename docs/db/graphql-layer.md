# GraphQL → DB layer (Pack 48-H Round 4 · #125)

## Contexto

Argus hoy expone REST (Flask `/api/...`). Si en el futuro se agrega GraphQL (Apollo, Strawberry, Graphene, Hasura, PostGraphile), las decisiones sobre cómo mapear a la DB importan.

Este doc no pide migrar a GraphQL. Documenta el camino si lo decidimos.

## Stack options

| Tool | Auto-genera schema desde DB? | Notas |
| --- | --- | --- |
| **Strawberry** (Python) | no (manual) | type-first, FastAPI friendly |
| **Graphene** (Python) | no | clásico Python |
| **Ariadne** (Python) | SDL-first | menos boilerplate |
| **Hasura** | **sí** (PG → GraphQL automático) | requiere su engine corriendo |
| **PostGraphile** | **sí** | igual, Node.js |
| **Apollo Federation** | no | para gateway multi-service |

## Auto-generated (Hasura/PostGraphile)

Pro:
- Cero código: cada tabla = type GraphQL.
- Subscriptions vía LISTEN/NOTIFY.
- RLS de PG se mapea automáticamente.

Contra:
- "Black-box" performance: complicado optimizar resolvers internos.
- Auth bridging custom (JWT claims → SET LOCAL app.company_id).
- Lock-in con el engine.

## Mapping types → tables

```graphql
type Scan {
  id: ID!
  startedAt: DateTime!
  verdict: Verdict
  riskScore: Float
  violations: [PluginViolation!]!  # resolver con JOIN o batched
  company: Company!                # resolver
  player: Player                   # resolver
}

type Company { id: ID!  name: String!  scans(limit: Int = 50): [Scan!]! }
type Player { uuid: ID!  name: String!  recentScans: [Scan!]! }
```

Reglas mapping:

| GraphQL | DB |
| --- | --- |
| field type primitive | columna |
| field type Object | FK + resolver |
| field type [Object!]! | reverse FK + resolver (paginate) |
| `Mutation` | INSERT/UPDATE/DELETE en una sola tx |
| `Subscription` | LISTEN canal + filtros |

## N+1 problem

GraphQL es notorio. Ejemplo:

```graphql
query { company { scans { violations { type } } } }
```

Resolvers naïve: 1 query company → N queries scan → M queries violations.

## Dataloader pattern

Batched + cached por request:

```python
class ViolationsByScanLoader(DataLoader):
    async def batch_load_fn(self, scan_ids):
        rows = await db.fetch(
            "SELECT scan_id, type, severity FROM plugin_violations WHERE scan_id = ANY($1)",
            list(scan_ids),
        )
        by_scan = {sid: [] for sid in scan_ids}
        for r in rows:
            by_scan[r["scan_id"]].append(r)
        return [by_scan[sid] for sid in scan_ids]

# en resolver:
def violations(scan, info):
    return info.context["loaders"].violations_by_scan.load(scan.id)
```

Reduce a 1 query batched para los N scans del request.

## Persisted queries

En lugar de aceptar queries arbitrarias, el cliente envía un **hash** y el server las resuelve a queries pre-aprobadas.

Beneficios:
- Reduce ancho de banda.
- Bloquea queries maliciosas / costosas.
- Permite caching server-side por hash.

Convención: archivar queries en `docs/graphql/queries/*.gql` + script que las hashea.

## Subscriptions vía LISTEN/NOTIFY

```python
async def on_scan_completed(scan_id, info):
    async with db.connection() as conn:
        await conn.execute("LISTEN argus_changes")
        while True:
            payload = await conn.notifies.get()
            if payload['table'] == 'scans' and payload['op'] == 'I':
                yield Scan(**payload)
```

Combinado con triggers `argus_notify_change()` (ver `triggers.sql` #120).

Limitaciones:
- LISTEN bloquea una conexión PG; con pool pequeño, problema.
- Para muchos subscribers: mover a Redis Streams (ver `cdc-design.md`).

## Auth / tenant context

Cada request GraphQL debe setear `SET LOCAL app.company_id` para RLS:

```python
@app.route("/graphql", methods=["POST"])
def gql():
    user = require_auth()
    with db.begin():
        db.execute(text("SELECT set_config('app.company_id', :v, false)"),
                   {"v": str(user.company_id)})
        return graphql_sync(schema, request.json["query"], context={"user": user})
```

Sin esto, RLS no protege nada.

## Query complexity / cost limiting

GraphQL clients pueden enviar queries profundamente anidadas. Mitigaciones:

- **Max depth** (típico 7-10).
- **Max nodes** (1000).
- **Cost analysis** (`graphql-cost-analysis`).
- **Statement timeout** PG (#111) protege independientemente.

## Caching layers

1. **Persisted queries** + CDN.
2. **Application-level** (Redis) por (query hash, args, tenant).
3. **DB-level**: MVs (#90) para hot dashboards.

## Cuándo evaluar GraphQL en Argus

| Trigger | ¿Adoptar GraphQL? |
| --- | --- |
| Frontend dispar (web + mobile + plugin) consume mismos datos | tal vez |
| Necesidad de queries ad-hoc por cliente | tal vez |
| Backend pequeño con 5 endpoints | no |
| Necesidad de subscriptions realtime sin armar WS custom | tal vez |
| Compliance pide audit completo de qué se consume | tal vez (persisted queries) |

**Hoy Argus**: no justificado. REST con OpenAPI cumple.

## Anti-patterns

1. ❌ Resolvers que abren conexión PG cada uno.
2. ❌ No usar dataloader → N+1 garantizado.
3. ❌ Aceptar queries arbitrarias en producción sin cost limits.
4. ❌ Exponer toda la tabla como type (incluye PII).
5. ❌ Subscriptions con LISTEN sin pool dedicado.

## Roadmap

- Pack 60+: si justifica, prototipo Strawberry + dataloader + persisted queries.
- Reusar `argus_notify_change()` (#120) para subscriptions.
- Auth: JWT → SET LOCAL app.company_id.
- Bench vs REST current; mantener ambos si conviene.

## Referencias

- `triggers.sql` (#120) — argus_notify_change.
- `cdc-design.md` (#92) — alternativa a subscriptions LISTEN.
- `security-hardening.md` (#108) — RLS context.
