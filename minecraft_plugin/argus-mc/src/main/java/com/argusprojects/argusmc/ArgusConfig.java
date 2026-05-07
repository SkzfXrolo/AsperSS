package com.argusprojects.argusmc;

import org.bukkit.configuration.file.FileConfiguration;

/**
 * Wrapper tipado sobre el config.yml. Vive el tiempo de un reload.
 */
public final class ArgusConfig {

    private final String baseUrl;
    private final String apiKey;
    private final int timeoutSeconds;

    private final boolean notifyTarget;
    private final int remindWindowMinutes;
    private final boolean broadcastToStaff;
    private final boolean requireReason;
    private final int minReasonLength;

    public ArgusConfig(FileConfiguration cfg) {
        String rawBase = cfg.getString("api.base_url", "https://asperss.onrender.com").trim();
        if (rawBase.endsWith("/")) {
            rawBase = rawBase.substring(0, rawBase.length() - 1);
        }
        this.baseUrl        = rawBase;
        this.apiKey         = cfg.getString("api.key", "").trim();
        this.timeoutSeconds = Math.max(3, cfg.getInt("api.timeout_seconds", 12));

        this.notifyTarget        = cfg.getBoolean("ss.notify_target", true);
        this.remindWindowMinutes = Math.max(1, cfg.getInt("ss.remind_window_minutes", 30));
        this.broadcastToStaff    = cfg.getBoolean("ss.broadcast_to_staff", true);
        this.requireReason       = cfg.getBoolean("ss.require_reason", false);
        this.minReasonLength     = Math.max(1, cfg.getInt("ss.min_reason_length", 4));
    }

    public boolean isMisconfigured() {
        return apiKey == null
            || apiKey.isEmpty()
            || apiKey.equalsIgnoreCase("REEMPLAZA_AQUI_TU_API_KEY")
            || !apiKey.startsWith("argus_pk_");
    }

    public String getBaseUrl() { return baseUrl; }
    public String getApiKey()  { return apiKey; }
    public int getTimeoutSeconds() { return timeoutSeconds; }

    public boolean isNotifyTarget()         { return notifyTarget; }
    public int     getRemindWindowMinutes() { return remindWindowMinutes; }
    public boolean isBroadcastToStaff()     { return broadcastToStaff; }
    public boolean isRequireReason()        { return requireReason; }
    public int     getMinReasonLength()     { return minReasonLength; }
}
