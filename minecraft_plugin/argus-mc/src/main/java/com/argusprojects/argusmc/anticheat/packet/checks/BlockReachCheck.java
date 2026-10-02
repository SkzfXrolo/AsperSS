package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Location;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class BlockReachCheck {

    private final ArgusPlugin plugin;

    public BlockReachCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleBlockInteract(Player player, PacketDataStore.State s,
                                    double bx, double by, double bz,
                                    ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("block_reach")) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("block_reach");
        double maxSurvival = sec != null ? sec.getDouble("max_survival", 5.5) : 5.5;
        double maxCreative = sec != null ? sec.getDouble("max_creative", 6.5) : 6.5;
        double extreme     = sec != null ? sec.getDouble("extreme", 7.5) : 7.5;

        double cap = (player.getGameMode() == GameMode.CREATIVE) ? maxCreative : maxSurvival;

        Location eye = player.getEyeLocation();

        double dx = eye.getX() - (bx + 0.5);
        double dy = eye.getY() - (by + 0.5);
        double dz = eye.getZ() - (bz + 0.5);
        double dist = Math.sqrt(dx * dx + dy * dy + dz * dz);

        if (dist >= extreme) {
            sink.flag(new Violation(player, "block_reach_packet",
                ViolationLevel.HIGH,
                String.format("block_dist=%.2f (>=%.2f)", dist, extreme)));
        } else if (dist > cap) {
            sink.flag(new Violation(player, "block_reach_packet",
                ViolationLevel.MID,
                String.format("block_dist=%.2f (>%.2f)", dist, cap)));
        }
    }
}
