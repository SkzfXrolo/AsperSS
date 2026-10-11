package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

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
