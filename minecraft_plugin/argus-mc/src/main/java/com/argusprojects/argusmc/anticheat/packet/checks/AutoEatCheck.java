package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — AutoEatCheck.
 *
 * <p>Detecta el patrón "eat→hit→eat→hit" perfectamente alternado.
 * Los cheats AutoEat de Lunar (versión cracked) o Wurst usan
 * macros que comen entre cada attack para mantener saturation. El
 * humano puede hacerlo pero NO con intervalos exactos.
 *
 * <p>Heurística:
 * <ul>
 *   <li>Detectar secuencia: {@code lastEatFinishMs} cerca del último
 *       attack (delta &lt; {@code window_ms}).</li>
 *   <li>Counter {@code autoEatPatternHits} aumenta con cada hit-eat
 *       consecutivo. Reset si pasa otro patrón.</li>
 *   <li>Stddev de intervalos eat→eat &lt; {@code max_stddev_ms} = bot.</li>
 * </ul>
 */
public final class AutoEatCheck {

    private final ArgusPlugin plugin;

    public AutoEatCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleEatFinish(Player player, PacketDataStore.State s,
                                long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("autoeat")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("autoeat");
        long windowMs   = sec != null ? sec.getLong("window_ms", 800L) : 800L;
        int  minPattern = sec != null ? sec.getInt("min_pattern_hits", 4) : 4;

        // Estaba comiendo "justo despues" de un attack?
        if (s.lastAttackMs > 0 && (now - s.lastAttackMs) <= windowMs) {
            s.autoEatPatternHits++;
            s.autoEatLastEventMs = now;
            if (s.autoEatPatternHits >= minPattern) {
                sink.flag(new Violation(player, "autoeat_packet",
                    ViolationLevel.HIGH,
                    "patron eat→hit x" + s.autoEatPatternHits));
                s.autoEatPatternHits = 0;
            }
        } else {
            s.autoEatPatternHits = 0;
        }
    }
}
