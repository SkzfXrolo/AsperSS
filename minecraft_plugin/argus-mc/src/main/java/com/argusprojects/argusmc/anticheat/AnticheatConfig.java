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
        this.lowAlertAt           = Math.max(1, cfg.getInt("anticheat.thresholds.low_alert_at", 1));
        this.midKickAt            = Math.max(1, cfg.getInt("anticheat.thresholds.mid_kick_at", 1));
        this.highForceSs          = Math.max(1, cfg.getInt("anticheat.thresholds.high_force_ss", 1));
        this.criticalBanAt        = Math.max(1, cfg.getInt("anticheat.thresholds.critical_ban_at", 1));
        this.criticalBanMinutes   = Math.max(1, cfg.getInt("anticheat.critical_ban_minutes", 60));
        this.violationWindowSeconds = Math.max(10, cfg.getInt("anticheat.violation_window_seconds", 60));
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
}
