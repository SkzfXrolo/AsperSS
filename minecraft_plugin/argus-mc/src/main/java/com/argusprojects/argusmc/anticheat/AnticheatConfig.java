package com.argusprojects.argusmc.anticheat;

import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.configuration.file.FileConfiguration;

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

    public ConfigurationSection checkSection(String name) {
        return root.getConfigurationSection("anticheat.checks." + name);
    }

    public boolean isCheckEnabled(String name) {
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("enabled", true);
    }

    public boolean isEnforcementForCheck(String name) {
        if (!enforcement) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("enforce", true);
    }

    public boolean isReportToBackendForCheck(String name) {
        if (!reportToBackend) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("report_to_backend", true);
    }

    public boolean isDiscordForCheck(String name) {
        if (!hasDiscordWebhook()) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("discord", true);
    }

    public boolean isAiOracleForCheck(String name) {
        if (!aiOracleEnabled) return false;
        ConfigurationSection s = checkSection(name);
        if (s == null) return true;
        return s.getBoolean("ai_oracle", true);
    }

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

    public String actionCapForCheck(String name) {
        ConfigurationSection s = checkSection(name);
        if (s == null) return null;
        String raw = s.getString("max_action", null);
        if (raw == null || raw.isEmpty() || raw.equalsIgnoreCase("none")) return null;
        return raw.toLowerCase();
    }
}
