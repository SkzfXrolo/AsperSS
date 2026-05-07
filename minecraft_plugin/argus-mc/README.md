# Argus MC — Plugin de Screen Share para Minecraft

Plugin Bukkit/Spigot/Paper que integra el comando `/ss <player>` con la
plataforma **Argus Projects**. Cuando un staff lo ejecuta:

1. El plugin contacta a la API de Argus con tu API key.
2. Argus genera un token de Screen Share de **6 caracteres** (1 uso, 30 min).
3. El staff recibe en chat el código + URL de descarga.
4. El target (opcionalmente) recibe la URL y el código por chat privado.
5. El panel de Argus registra **quién** generó el token (staff) y **a quién** se le pidió SS.

Compatible con **LuckyPerms** (los permisos respetan tus grupos LP).

---

## Requisitos

- Servidor Minecraft Java **Spigot / Paper / Purpur** 1.19+ (api-version 1.19).
- Java 17 o superior en el server.
- Tu servidor con conexión saliente HTTPS hacia `asperss.onrender.com` (o tu instancia self-hosted).
- Una **API key** generada desde el panel staff de Argus.

> LuckyPerms **NO es obligatorio**. Si no está, el plugin usa los defaults
> de `plugin.yml` (los OPs pueden usar `/ss`). Si LuckyPerms está, los
> permisos `argus.ss.use`, `argus.ss.bypass` y `argus.admin` se pueden
> asignar a tus grupos como cualquier otro permiso.

---

## Build

```bash
cd minecraft_plugin/argus-mc
mvn clean package
```

El `.jar` resultante queda en `target/argus-mc-1.0.0.jar`.

---

## Instalación

1. Copia `argus-mc-1.0.0.jar` a `plugins/` de tu server.
2. Inicia el server una vez para que se genere `plugins/ArgusMC/config.yml`.
3. Pega tu API key (`api.key`) en ese archivo. Asegúrate de que empieza con `argus_pk_`.
4. Reinicia el server **o** ejecuta `/argus reload`.
5. Prueba con `/argus test` — debe responder `Todo OK`.

---

## Cómo obtener la API key

Desde el panel staff de Argus:

1. Inicia sesión como **admin de empresa** o **owner**.
2. Ve a la sección "Plugin keys" (panel admin).
3. Crea una nueva key con un label descriptivo (ej: "Server Hispano - Plugin"). Sugerido:
    - `daily_quota`: ~200/día por servidor (ajustable).
4. **Copia la key completa** que se muestra. Solo se muestra **una vez**, no se podrá ver de nuevo.
5. Pega esa key en `config.yml` del plugin.

Si la pierdes: revoca la antigua desde el panel y crea una nueva.

> **Multi-tenant**: si tienes varias empresas o varios servers Minecraft,
> genera una key distinta para cada uno. El backend rastrea automáticamente
> qué token salió de qué key/server.

---

## Comandos

| Comando | Permiso | Descripción |
|---|---|---|
| `/ss <player> [razón]` | `argus.ss.use` | Genera código de SS y lo envía al staff (y opcionalmente al target). |
| `/argus reload` | `argus.admin` | Recarga `config.yml` sin reiniciar. |
| `/argus info` | `argus.admin` | Muestra estado de conexión, empresa, quota usada/disponible. |
| `/argus test` | `argus.admin` | Health check rápido contra la API. |

### Permisos

| Permiso | Default | Para qué sirve |
|---|---|---|
| `argus.ss.use` | OP | Permite usar `/ss`. |
| `argus.ss.bypass` | nadie | Exime al jugador de poder ser objetivo de `/ss` (útil para staff senior). |
| `argus.ss.notify` | nadie | Recibe el broadcast cuando otro staff ejecuta `/ss`. |
| `argus.admin` | OP | Permite usar `/argus`. |

---

## Ejemplo (LuckyPerms)

```bash
# Asignar permisos al grupo "moderator"
lp group moderator permission set argus.ss.use true
lp group moderator permission set argus.ss.notify true

# Solo "admin" puede ver el panel del plugin
lp group admin permission set argus.admin true

# El owner es inmune a /ss
lp user MiOwner permission set argus.ss.bypass true
```

---

## Configuración (`config.yml`)

Las claves importantes:

```yaml
api:
  base_url: "https://asperss.onrender.com"
  key: "argus_pk_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"
  timeout_seconds: 12

ss:
  notify_target: true          # el target recibe la URL y el código
  broadcast_to_staff: true     # otros staff con argus.ss.notify lo ven
  require_reason: false        # exigir razón al ejecutar /ss
  min_reason_length: 4
```

Todos los textos se pueden personalizar bajo `messages:` (admite códigos
de color `&` de Bukkit).

---

## Diagnóstico

| Síntoma | Causa probable | Solución |
|---|---|---|
| `El plugin no esta configurado` | `api.key` vacía o sin prefijo | Pega la key real en `config.yml` y `/argus reload`. |
| `API key invalida` | Key revocada o mal copiada | Verifica el prefijo `argus_pk_`. Si fue revocada, genera otra. |
| `Quota diaria excedida` | Demasiadas emisiones hoy | Espera al reset de medianoche o pídele al admin que suba `daily_quota`. |
| `Error contactando a Argus` | Server sin internet o firewall | Asegúrate de que el server tenga acceso HTTPS al endpoint configurado. |

---

## Privacidad

El plugin **solo** envía:
- Nombre del staff que ejecutó `/ss` (Minecraft username).
- Nombre del target (Minecraft username).
- Razón opcional.
- IP del server (a través de la conexión HTTP).

No envía coordenadas, IPs de jugadores, ni ningún otro dato del server.

---

## Licencia

Mismo proyecto que Argus Projects. Uso libre para clientes con suscripción
activa (Pro o Empresa).
