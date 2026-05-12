package com.argusprojects.argusmc.anticheat;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

/**
 * Wrapper tipado sobre la seccion `anticheat:` del config.yml.
 *
 * <p>Cada check lee sus propios sub-valores via {@link #checkSection(String)}
 * para no acoplarse a esta clase. Esta clase solo expone los valores globales.
 */
public final class AnticheatConfig {

    private final FileConfiguration root;
    private final boolean enabled;
    private final boolean enforcement;

    private final int lowAlertAt;
    private final int midKickAt;
    private final int highForceSs;
    private final int criticalBanAt;
    private final int criticalBanMinutes;
    private final int violationWindowSeconds;

    private final boolean reportToBackend;
    private final String discordWebhookUrl;
    private final boolean aiOracleEnabled;

    public AnticheatConfig(FileConfiguration cfg) {
        this.root = cfg;
        this.enabled              = cfg.getBoolean("anticheat.enabled", true);
        this.enforcement          = cfg.getBoolean("anticheat.enforcement", true);
        // Defaults Pack 44.2: thresholds CONSERVADORES para evitar false
        // positives. Es preferible un cheater que se cuela 30 segundos a un
        // jugador legitimo kickeado erroneamente. Para servers PvP estrictos,
        // bajar manualmente en config.yml.
        this.lowAlertAt           = Math.max(1, cfg.getInt("anticheat.thresholds.low_alert_at", 3));
        this.midKickAt            = Math.max(1, cfg.getInt("anticheat.thresholds.mid_kick_at", 3));
        this.highForceSs          = Math.max(1, cfg.getInt("anticheat.thresholds.high_force_ss", 2));
        this.criticalBanAt        = Math.max(1, cfg.getInt("anticheat.thresholds.critical_ban_at", 2));
        this.criticalBanMinutes   = Math.max(1, cfg.getInt("anticheat.critical_ban_minutes", 60));
        this.violationWindowSeconds = Math.max(10, cfg.getInt("anticheat.violation_window_seconds", 90));
        this.reportToBackend      = cfg.getBoolean("anticheat.report_to_backend", true);
        this.discordWebhookUrl    = cfg.getString("anticheat.discord_webhook_url", "").trim();
        this.aiOracleEnabled      = cfg.getBoolean("anticheat.ai_oracle_enabled", true);
    }

    public boolean isEnabled() { return enabled; }
    public boolean isEnforcement() { return enforcement; }

    public int getLowAlertAt() { return lowAlertAt; }
    public int getMidKickAt() { return midKickAt; }
    public int getHighForceSs() { return highForceSs; }
    public int getCriticalBanAt() { return criticalBanAt; }
    public int getCriticalBanMinutes() { return criticalBanMinutes; }
    public int getViolationWindowSeconds() { return violationWindowSeconds; }

    public boolean isReportToBackend() { return reportToBackend; }
    public String getDiscordWebhookUrl() { return discordWebhookUrl; }
    public boolean hasDiscordWebhook() {
        return discordWebhookUrl != null && !discordWebhookUrl.isEmpty();
    }
    public boolean isAiOracleEnabled() { return aiOracleEnabled; }

    /** Subseccion de un check concreto (ej: "reach", "killaura_angle"). */
    public ConfigurationSection checkSection(String name) {
        ConfigurationSection s = root.getConfigurationSection("anticheat.checks." + name);
        return s; // puede ser null; los checks deben usar getOrDefault
    }

    /** Util: leer si un check esta enabled (default true si no esta listado). */
    public boolean isCheckEnabled(String name) {
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("enabled", true);
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Pack 48 #521-#526 — Per-check enforcement / behaviour flags.
    //
    //  Permite que cada check tenga overrides individuales sin tocar el
    //  switch global. Util por ejemplo cuando un check nuevo (fast_break)
    //  da algun false-positive y queres dejarlo en modo observer mientras
    //  los demas siguen kickeando.
    // ──────────────────────────────────────────────────────────────────────

    /**
     * #521 — Per-check enforcement: si false, este check JAMAS dispara
     * kick/ban/SS, solo broadcast a staff. Cae a la flag global por defecto.
     */
    public boolean isEnforcementForCheck(String name) {
        if (!enforcement) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("enforce", true);
    }

    /**
     * #522 — Per-check report_to_backend: si false, el plugin NO envia esta
     * violation al backend (util para checks ruidosos que no quieren saturar
     * la BD remota).
     */
    public boolean isReportToBackendForCheck(String name) {
        if (!reportToBackend) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("report_to_backend", true);
    }

    /**
     * #523 — Per-check discord webhook: si false, no envia esta violation
     * al webhook de Discord configurado globalmente.
     */
    public boolean isDiscordForCheck(String name) {
        if (!hasDiscordWebhook()) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("discord", true);
    }

    /**
     * #524 — Per-check AI Oracle: si false, las violations de este check
     * NO se mandan al Oracle (ahorra quota si un check ya es 100% confiable
     * o si tira muchos FPs y no queres alimentar al modelo con basura).
     */
    public boolean isAiOracleForCheck(String name) {
        if (!aiOracleEnabled) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("ai_oracle", true);
    }

    /**
     * #525 — Per-check level override: permite forzar todas las violations
     * de un check a un nivel concreto (LOW/MID/HIGH/CRITICAL) sin recompilar.
     * Devuelve null si no hay override.
     */
    public ViolationLevel levelOverrideForCheck(String name) {
        ConfigurationSection s = checkSection(name);
        if (s == null) return null;
        String raw = s.getString("force_level", null);
        if (raw == null || raw.isEmpty()) return null;
        try {
            return ViolationLevel.valueOf(raw.toUpperCase());
        } catch (IllegalArgumentException ex) {
            return null;
        }
    }

    /**
     * #526 — Per-check action cap: permite limitar la accion maxima que
     * puede tomar este check, independientemente del nivel acumulado.
     * Valores: "watch", "ss", "kick", "ban" (case-insensitive), o null/none
     * para sin cap. Util para checks nuevos en periodo de calibracion.
     */
    public String actionCapForCheck(String name) {
        ConfigurationSection s = checkSection(name);
        if (s == null) return null;
        String raw = s.getString("max_action", null);
        if (raw == null || raw.isEmpty() || raw.equalsIgnoreCase("none")) return null;
        return raw.toLowerCase();
    }
}
