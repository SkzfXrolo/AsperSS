package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 round 3 — AutoPotionCheck.
 *
 * <p>"AutoPot" bot toma una poción de healing instantáneamente al
 * recibir un golpe. En vanilla beber pot tarda 1.61s (igual que comer)
 * y no se puede iniciar mientras te empujan con KB activo.
 *
 * <p>Reutiliza el campo {@code useItemStartMs}/{@code useItemMaterial}
 * actualizados por el bridge en {@code PlayerInteractEvent} cuando el
 * item de mano es una poción.
 *
 * <p>Heurística: si {@code useItemMaterial} matchea
 * {@code splash_potion|potion|lingering_potion} y el inicio del use
 * ocurre &lt; {@code max_reaction_ms} (default 200ms) tras el último
 * daño, flag.
 */
public final class AutoPotionCheck {

    private final ArgusPlugin plugin;

    public AutoPotionCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleUseStart(Player player, PacketDataStore.State s,
                               String materialName, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("autopotion")) return;
        if (materialName == null) return;
        String m = materialName.toUpperCase();
        boolean isPot = m.equals("POTION") || m.equals("SPLASH_POTION")
                      || m.equals("LINGERING_POTION");
        if (!isPot) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("autopotion");
        long maxReaction = sec != null ? sec.getLong("max_reaction_ms", 200L) : 200L;
        long extreme     = sec != null ? sec.getLong("extreme_ms", 80L) : 80L;

        long sinceDamage = s.lastDamageTakenMs == 0 ? Long.MAX_VALUE
                                                     : (now - s.lastDamageTakenMs);
        if (sinceDamage < extreme) {
            sink.flag(new Violation(player, "autopotion_packet",
                ViolationLevel.HIGH,
                "pot drink " + sinceDamage + "ms post-hit (super-human)"));
        } else if (sinceDamage < maxReaction) {
            sink.flag(new Violation(player, "autopotion_packet",
                ViolationLevel.MID,
                "pot drink " + sinceDamage + "ms post-hit"));
        }
    }
}
