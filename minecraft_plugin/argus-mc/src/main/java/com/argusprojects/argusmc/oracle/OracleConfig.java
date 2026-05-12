package com.argusprojects.argusmc.oracle;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.configuration.ConfigurationSection;

/**
 * Pack 48 round 3 — Configuración opt-in de la integración con
 * Argus Oracle ML (web_app/backend).
 *
 * <p>Snapshot de los valores de {@code config.yml::oracle}:
 * <pre>
 * oracle:
 *   enabled: false
 *   url: "https://argus.example.com/api/oracle/evaluate-mc-violation"
 *   api_key: "REEMPLAZA"
 *   timeout_ms: 1500
 *   cache_ttl_ms: 30000
 *   weight_floor: 0.6      # min weight aplicado a severidad
 *   weight_ceiling: 1.5    # max weight (boost para "casi seguro cheat")
 *   heartbeat_interval_s: 60
 *   heartbeat_url: "https://argus.example.com/api/oracle/heartbeat-mc"
 * </pre>
 */
public final class OracleConfig {

    public final boolean enabled;
    public final String  url;
    public final String  apiKey;
    public final long    timeoutMs;
    public final long    cacheTtlMs;
    public final double  weightFloor;
    public final double  weightCeiling;
    public final long    heartbeatIntervalSec;
    public final String  heartbeatUrl;

    private OracleConfig(boolean enabled, String url, String key, long timeout,
                         long cacheTtl, double wFloor, double wCeil,
                         long hbInterval, String hbUrl) {
        this.enabled = enabled;
        this.url = url;
        this.apiKey = key;
        this.timeoutMs = timeout;
        this.cacheTtlMs = cacheTtl;
        this.weightFloor = wFloor;
        this.weightCeiling = wCeil;
        this.heartbeatIntervalSec = hbInterval;
        this.heartbeatUrl = hbUrl;
    }

    public static OracleConfig fromPlugin(ArgusPlugin plugin) {
        ConfigurationSection sec = plugin.getConfig().getConfigurationSection("oracle");
        if (sec == null) {
            return new OracleConfig(false, "", "", 1500L, 30_000L,
                0.6, 1.5, 60L, "");
        }
        return new OracleConfig(
            sec.getBoolean("enabled", false),
            sec.getString("url", ""),
            sec.getString("api_key", ""),
            sec.getLong("timeout_ms", 1500L),
            sec.getLong("cache_ttl_ms", 30_000L),
            sec.getDouble("weight_floor", 0.6),
            sec.getDouble("weight_ceiling", 1.5),
            sec.getLong("heartbeat_interval_s", 60L),
            sec.getString("heartbeat_url", "")
        );
    }

    public boolean hasValidUrl() {
        return enabled && url != null && !url.isEmpty() && apiKey != null && !apiKey.isEmpty();
    }
}
