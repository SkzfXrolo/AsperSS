package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

public final class AutoTotemCheck {

    private final ArgusPlugin plugin;

    public AutoTotemCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleOffhandUpdate(Player player, PacketDataStore.State s, long now,
                                    ItemStack resultingOffhand, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("auto_totem")) return;
        if (resultingOffhand == null) return;
        if (resultingOffhand.getType() != Material.TOTEM_OF_UNDYING) return;

        if (s.lastDamageTakenMs == 0L) return;
        long sinceHit = now - s.lastDamageTakenMs;
        if (sinceHit < 0L || sinceHit > 600L) return;

        double healthAfterDmg = s.lastDamageHealthAfter;
        if (healthAfterDmg > 4.0) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("auto_totem");
        long fastMs    = sec != null ? sec.getLong("react_ms_fast",    50L)  : 50L;
        long midMs     = sec != null ? sec.getLong("react_ms_mid",     100L) : 100L;
        long slowMs    = sec != null ? sec.getLong("react_ms_slow",    200L) : 200L;

        if (sinceHit < fastMs) {
            sink.flag(new Violation(player, "auto_totem_packet",
                ViolationLevel.HIGH,
                String.format("react=%dms healthAfter=%.1f (<%dms threshold)",
                    sinceHit, healthAfterDmg, fastMs)));
        } else if (sinceHit < midMs) {
            sink.flag(new Violation(player, "auto_totem_packet",
                ViolationLevel.MID,
                String.format("react=%dms healthAfter=%.1f", sinceHit, healthAfterDmg)));
        } else if (sinceHit < slowMs) {
            sink.flag(new Violation(player, "auto_totem_packet",
                ViolationLevel.LOW,
                String.format("react=%dms healthAfter=%.1f", sinceHit, healthAfterDmg)));
        }
    }
}
