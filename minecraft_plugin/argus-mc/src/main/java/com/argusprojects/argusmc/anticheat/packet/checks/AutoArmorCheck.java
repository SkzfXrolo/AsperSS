package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — AutoArmorCheck.
 *
 * <p>"AutoArmor" cheats equipan armor en milisegundos al recibir un
 * golpe. Vanilla requiere abrir inventory (slowdown + animación), arrastrar
 * la pieza, cerrar inventory. Imposible en &lt; 250ms.
 *
 * <p>Detección: el bridge llama {@link #handleArmorChange} cuando ve
 * un cambio en cualquier slot de armor. Si el cambio ocurre dentro
 * de {@code combat_window_ms} (default 3s) tras el último daño y la
 * diferencia entre cambios consecutivos es &lt; {@code min_change_interval_ms}
 * (default 300ms), flag.
 */
public final class AutoArmorCheck {

    private final ArgusPlugin plugin;

    public AutoArmorCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleArmorChange(Player player, PacketDataStore.State s,
                                  long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("autoarmor")) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("autoarmor");
        long combatWindow = sec != null ? sec.getLong("combat_window_ms", 3_000L) : 3_000L;
        long minInterval  = sec != null ? sec.getLong("min_change_interval_ms", 300L) : 300L;

        long sinceDamage = s.lastDamageTakenMs == 0 ? Long.MAX_VALUE : (now - s.lastDamageTakenMs);
        long sinceLastChange = s.lastArmorChangeMs == 0 ? Long.MAX_VALUE
                                                        : (now - s.lastArmorChangeMs);
        s.lastArmorChangeMs = now;

        if (sinceDamage > combatWindow) return; // no en combate.
        if (sinceLastChange < minInterval) {
            sink.flag(new Violation(player, "autoarmor_packet",
                ViolationLevel.HIGH,
                "armor changed dt=" + sinceLastChange + "ms en combate (post-hit=" + sinceDamage + "ms)"));
        } else if (sinceLastChange < combatWindow / 2) {
            sink.flag(new Violation(player, "autoarmor_packet",
                ViolationLevel.MID,
                "armor changed mid-combate dt=" + sinceLastChange + "ms"));
        }
    }
}
