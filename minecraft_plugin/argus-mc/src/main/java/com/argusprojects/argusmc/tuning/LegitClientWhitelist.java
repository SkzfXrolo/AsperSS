package com.argusprojects.argusmc.tuning;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

import java.util.Locale;

/**
 * Pack 48 round 3 — Reconoce clients "legit" (Lunar, Forge vanilla,
 * Optifine, Badlion) y aplica un multiplier suave sobre los thresholds
 * de movimiento/combate.
 *
 * <p>El brand del cliente lo entrega Mojang via plugin-message
 * {@code minecraft:brand} al join — lo guarda
 * {@link com.argusprojects.argusmc.anticheat.packet.PacketAnticheatBukkitBridge}
 * en {@link PacketDataStore.State#clientBrand}.
 *
 * <h3>Whitelist y multiplier</h3>
 * <p>Default whitelist: vanilla, fabric, forge, optifine, lunarclient,
 * badlion. Si el brand matchea, se aplica
 * {@code tuning.client_whitelist.relaxation_multiplier} (default 1.10)
 * — equivale a "este jugador tiene 10% más tolerancia antes de flag".
 *
 * <p>NOTA: el client brand es <b>spoofable</b>. Por eso solo aplicamos
 * un boost suave, nunca un bypass total.
 */
public final class LegitClientWhitelist {

    private final ArgusPlugin plugin;

    public LegitClientWhitelist(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** Multiplier sobre el threshold para este player (1.0 = sin cambio). */
    public double thresholdMultiplier(Player p) {
        if (p == null) return 1.0;
        ConfigurationSection sec = plugin.getConfig()
            .getConfigurationSection("tuning.client_whitelist");
        if (sec == null || !sec.getBoolean("enabled", false)) return 1.0;

        var bs = plugin.getPacketEventsBootstrap();
        PacketDataStore.State s = bs != null && bs.getDataStore() != null
            ? bs.getDataStore().peek(p.getUniqueId()) : null;
        String brand = s != null ? s.clientBrand : null;
        if (brand == null || brand.isEmpty()) return 1.0;

        brand = brand.toLowerCase(Locale.ROOT);
        var whitelisted = sec.getStringList("brands");
        if (whitelisted.isEmpty()) {
            whitelisted = java.util.Arrays.asList(
                "vanilla", "fabric", "forge", "optifine", "lunarclient", "badlion");
        }
        for (String w : whitelisted) {
            if (brand.contains(w.toLowerCase(Locale.ROOT))) {
                return sec.getDouble("relaxation_multiplier", 1.10);
            }
        }
        return 1.0;
    }

    public boolean isLegitClient(Player p) {
        return thresholdMultiplier(p) > 1.0;
    }
}
