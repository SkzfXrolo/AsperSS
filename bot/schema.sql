-- ═══════════════════════════════════════════════════════════════════════
-- Schema del bot de Discord — Argus Projects
-- Idempotente: se aplica cada vez que arranca el bot.
-- Todas las tablas usan prefijo bot_ para no chocar con el web app.
-- ═══════════════════════════════════════════════════════════════════════

-- ── Settings genericos por guild (key/value) ──────────────────────────
CREATE TABLE IF NOT EXISTS bot_settings (
    guild_id   BIGINT NOT NULL,
    key        VARCHAR(100) NOT NULL,
    value      TEXT,
    updated_at TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (guild_id, key)
);

-- ── Warns / strikes ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_warns (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    reason      TEXT,
    created_at  TIMESTAMP DEFAULT NOW(),
    expires_at  TIMESTAMP,
    active      BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_bot_warns_guild_user ON bot_warns(guild_id, user_id) WHERE active = TRUE;

-- ── Acciones de moderacion (audit log) ────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_modlog (
    id           BIGSERIAL PRIMARY KEY,
    guild_id     BIGINT NOT NULL,
    user_id      BIGINT NOT NULL,
    moderator_id BIGINT NOT NULL,
    action       VARCHAR(20) NOT NULL,  -- warn|mute|kick|ban|unban|unmute|clear
    reason       TEXT,
    duration     INTERVAL,
    created_at   TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bot_modlog_guild_user ON bot_modlog(guild_id, user_id);

-- ── XP / niveles / monedas ────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_xp (
    guild_id     BIGINT NOT NULL,
    user_id      BIGINT NOT NULL,
    xp           BIGINT DEFAULT 0,
    level        INT DEFAULT 0,
    coins        BIGINT DEFAULT 0,
    last_message TIMESTAMP DEFAULT NOW(),
    messages     BIGINT DEFAULT 0,
    PRIMARY KEY (guild_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_bot_xp_leaderboard ON bot_xp(guild_id, xp DESC);

-- ── Tienda (items que se compran con monedas) ─────────────────────────
CREATE TABLE IF NOT EXISTS bot_shop_items (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    name        VARCHAR(100) NOT NULL,
    description TEXT,
    price       BIGINT NOT NULL,
    role_id     BIGINT,         -- opcional: si se compra, otorga este rol
    stock       INT DEFAULT -1, -- -1 = infinito
    created_at  TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS bot_shop_purchases (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    item_id     BIGINT REFERENCES bot_shop_items(id) ON DELETE SET NULL,
    price_paid  BIGINT NOT NULL,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ── Tickets ───────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_tickets (
    id           BIGSERIAL PRIMARY KEY,
    guild_id     BIGINT NOT NULL,
    channel_id   BIGINT NOT NULL,
    user_id      BIGINT NOT NULL,
    category     VARCHAR(50),
    status       VARCHAR(20) DEFAULT 'open',  -- open|closed
    created_at   TIMESTAMP DEFAULT NOW(),
    closed_at    TIMESTAMP,
    closed_by    BIGINT,
    transcript   TEXT
);
CREATE INDEX IF NOT EXISTS idx_bot_tickets_user ON bot_tickets(guild_id, user_id, status);

-- ── Eventos / sorteos ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_events (
    id           BIGSERIAL PRIMARY KEY,
    guild_id     BIGINT NOT NULL,
    channel_id   BIGINT NOT NULL,
    message_id   BIGINT,
    type         VARCHAR(20) NOT NULL,  -- giveaway|tournament|quiz
    title        VARCHAR(200) NOT NULL,
    description  TEXT,
    prize        TEXT,
    winner_count INT DEFAULT 1,
    created_by   BIGINT NOT NULL,
    starts_at    TIMESTAMP DEFAULT NOW(),
    ends_at      TIMESTAMP NOT NULL,
    finished     BOOLEAN DEFAULT FALSE,
    winners      TEXT,
    extra        TEXT
);
CREATE INDEX IF NOT EXISTS idx_bot_events_pending ON bot_events(guild_id, finished, ends_at);

CREATE TABLE IF NOT EXISTS bot_event_participants (
    event_id   BIGINT NOT NULL REFERENCES bot_events(id) ON DELETE CASCADE,
    user_id    BIGINT NOT NULL,
    joined_at  TIMESTAMP DEFAULT NOW(),
    PRIMARY KEY (event_id, user_id)
);

-- ── Autoroles (paneles persistentes con botones / select menus) ───────
CREATE TABLE IF NOT EXISTS bot_autorole_panels (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    channel_id  BIGINT NOT NULL,
    message_id  BIGINT NOT NULL,
    title       VARCHAR(200),
    description TEXT,
    style       VARCHAR(20) DEFAULT 'buttons', -- buttons|select
    role_data   TEXT NOT NULL                  -- JSON: [{"role_id":..., "label":..., "emoji":..., "description":...}]
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_bot_autorole_panels_msg ON bot_autorole_panels(guild_id, message_id);

-- ── Verificacion (captchas pendientes) ────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_verifications (
    user_id     BIGINT NOT NULL,
    guild_id    BIGINT NOT NULL,
    code        VARCHAR(20) NOT NULL,
    attempts    INT DEFAULT 0,
    created_at  TIMESTAMP DEFAULT NOW(),
    expires_at  TIMESTAMP NOT NULL,
    PRIMARY KEY (user_id, guild_id)
);

-- ── Counting game ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS bot_counting (
    guild_id     BIGINT PRIMARY KEY,
    channel_id   BIGINT NOT NULL,
    current      BIGINT DEFAULT 0,
    last_user_id BIGINT,
    record       BIGINT DEFAULT 0,
    record_at    TIMESTAMP
);

-- ── Setup log (historial de /setup y /reset ejecutados) ───────────────
CREATE TABLE IF NOT EXISTS bot_setup_log (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    executed_by BIGINT NOT NULL,
    action      VARCHAR(20) NOT NULL,  -- setup|reset
    summary     TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);

-- ── Automod (estado por canal/usuario para anti-spam) ─────────────────
CREATE TABLE IF NOT EXISTS bot_automod_violations (
    id          BIGSERIAL PRIMARY KEY,
    guild_id    BIGINT NOT NULL,
    user_id     BIGINT NOT NULL,
    channel_id  BIGINT,
    rule        VARCHAR(50) NOT NULL,  -- spam|link|mention|caps|word_filter|raid
    content     TEXT,
    created_at  TIMESTAMP DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_bot_automod_user ON bot_automod_violations(guild_id, user_id, created_at DESC);
