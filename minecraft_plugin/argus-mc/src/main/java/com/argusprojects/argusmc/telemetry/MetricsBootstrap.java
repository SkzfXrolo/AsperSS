package com.argusprojects.argusmc.telemetry;

import com.argusprojects.argusmc.ArgusPlugin;
import org.bukkit.Bukkit;

import java.util.HashMap;
import java.util.Map;

/**
 * Pack 48 round 2 — Init de bStats Metrics desde {@link ArgusPlugin#onEnable()}.
 *
 * <p>Lee {@code metrics.enabled} (default true) y, si esta on, registra
 * charts utiles:
 * <ul>
 *   <li><b>player_count_bucket</b> — bucket de tamano del server.</li>
 *   <li><b>checks_enabled</b> — map de check_name -> 1 si esta on.</li>
 *   <li><b>enforcement_mode</b> — "observer" o "enforce".</li>
 *   <li><b>packetevents_present</b> — 1 si PacketEvents soft-dep esta activo.</li>
 * </ul>
 */
public final class MetricsBootstrap {

    public static Metrics init(ArgusPlugin plugin) {
        boolean enabled = plugin.getConfig().getBoolean("metrics.enabled", true);
        if (!enabled) {
            plugin.getLogger().info("[Argus/Metrics] disabled via config (metrics.enabled=false).");
            return null;
        }
        Metrics m = new Metrics(plugin);
        // Bucket de tamano del server (player count categorizado).
        m.addCustomChart("player_count_bucket", () -> {
            int n = Bukkit.getOnlinePlayers().size();
            if (n == 0) return "0";
            if (n < 5)  return "1-4";
            if (n < 15) return "5-14";
            if (n < 50) return "15-49";
            if (n < 200) return "50-199";
            return "200+";
        });
        // Enforcement mode
        m.addCustomChart("enforcement_mode", () ->
            plugin.getAnticheatConfig() != null && plugin.getAnticheatConfig().isEnforcement()
                ? "enforce" : "observer");
        // PacketEvents soft-dep present
        m.addCustomChart("packetevents_present", () ->
            plugin.getPacketEventsBootstrap() != null
                && plugin.getPacketEventsBootstrap().isInitialized() ? 1 : 0);
        // Checks enabled — map.
        m.addCustomChart("checks_enabled", () -> {
            Map<String, Integer> out = new HashMap<>();
            if (plugin.getAnticheatConfig() == null) return out;
            String[] names = {
                "timer","phase","velocity","invalid_rotation","reach_packet","killaura_swing_packet",
                "aim_snap_packet","ping_spoof","cps_packet","inv_move_packet",
                "vclip","step","speed_packet","fast_place","fast_break","nuker","auto_totem",
                "killaura_aim","killaura_blocking","boat_fly","jetpack","spider",
                "multi_velocity","block_reach","crit","projectile_aim","bow_aim","boat_fly_advanced",
                "hitbox_expansion","backstab","melee_fly",
                "block_glitch","item_pickup","inventory_teleport","liquid_walk",
                "chat_macro","named_item_spam","autoclicker_advanced"
            };
            for (String n : names) {
                if (plugin.getAnticheatConfig().isCheckEnabled(n)) out.put(n, 1);
            }
            return out;
        });
        m.start();
        plugin.getLogger().info("[Argus/Metrics] bStats-compatible telemetry ON (opt-out: metrics.enabled=false).");
        return m;
    }
}
