# Argus Discord Bot

Bot de comunidad para **Argus Projects**: setup automático del servidor,
moderación, automod, autoroles, XP/economía, juegos, eventos, tickets y
comandos integrados con el panel staff (`/scan`, `/veredicto`, `/ss`).

## Setup rápido (Windows local)

1. **Crear el bot en Discord**
   - Ir a https://discord.com/developers/applications
   - `New Application` → ponerle nombre (ej. *Argus*)
   - Tab **Bot** → `Add Bot` → copiar el **Token**
   - Activar **Privileged Gateway Intents**:
     - ✅ `Server Members Intent`
     - ✅ `Message Content Intent`
   - Tab **OAuth2 → URL Generator**:
     - Scopes: `bot`, `applications.commands`
     - Bot Permissions: `Administrator` (más simple) o seleccionar manualmente
       `Manage Channels`, `Manage Roles`, `Kick Members`, `Ban Members`,
       `Manage Messages`, `Send Messages`, `Embed Links`, `Add Reactions`,
       `Use Slash Commands`, `Manage Webhooks`
   - Copiar la URL generada y pegarla en el navegador → invitar al bot a tu server.

2. **Configurar `.env`**
   ```bash
   cd bot
   copy .env.example .env
   notepad .env
   ```
   Rellenar como mínimo:
   - `DISCORD_TOKEN` (el token del paso 1)
   - `DISCORD_GUILD` (ID del server: click derecho → Copy Server ID con Modo Desarrollador)
   - `DATABASE_URL` (Postgres external URL de Render — ya viene de ejemplo)

3. **Arrancar**
   - Doble click en `bot\start_bot.bat`, o desde terminal:
     ```bash
     python -m bot
     ```

4. **Setup del servidor**
   - En Discord, ejecutar `/setup` (requiere Administrator).
   - El bot crea categorías, canales y roles desde cero (modo destructivo).

## Estructura

```
bot/
  main.py              entrypoint, carga cogs, sync slash commands
  config.py            lee .env y expone constantes
  db.py                pool psycopg2 + helpers
  utils.py             embeds branded, parsers de duración, helpers
  schema.sql           tablas bot_* (idempotente)
  cogs/
    setup.py           /setup destructivo
    welcome.py         bienvenida + captcha + autorole al verificar
    moderation.py      /warn /mute /kick /ban /unmute /clear + strikes
    automod.py         anti-spam, anti-link, anti-raid, filtros de palabras
    autoroles.py       paneles con botones / select menus
    economy.py         XP, niveles, monedas, tienda
    games.py           /trivia /counting /blackjack /ahorcado
    events.py          /sorteo /torneo programados
    tickets.py         panel con botón → canal privado → /close
    argus.py           /scan /veredicto /ss /stats (integrado con web app)
```

## Tablas BD

Todas con prefijo `bot_` para no chocar con el web app:
`bot_settings`, `bot_warns`, `bot_modlog`, `bot_xp`, `bot_shop_items`,
`bot_tickets`, `bot_events`, `bot_autorole_panels`, `bot_verifications`,
`bot_counting`, `bot_setup_log`, `bot_automod_violations`.

Se aplican automáticamente al arrancar (idempotentes).

## Migrar a host estable

Cuando consigas VPS/fly.io/railway:
1. Copiar la carpeta `bot/` al servidor (o clonar el repo).
2. `pip install -r bot/requirements.txt`
3. Crear `.env` con los mismos valores.
4. Arrancar con `python -m bot` (idealmente bajo `systemd`, `pm2` o `tmux`).

No requiere cambios de código — solo cambia el host.

## Logs

Por defecto el bot imprime logs en stdout con nivel INFO.
Para más detalle: `BOT_DEBUG=1` en `.env`.
