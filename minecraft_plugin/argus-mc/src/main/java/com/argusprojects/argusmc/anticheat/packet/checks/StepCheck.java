package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class StepCheck {

    private static final long FROM_GROUND_WINDOW_MS = 120L;

    private final ArgusPlugin plugin;

    public StepCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     boolean nowOnGround,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("step")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "step")) return;
        if (s.teleporting) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.getAllowFlight() && player.isFlying()) return;
        if (player.isInsideVehicle()) return;
        if (player.isGliding()) return;
        if (player.isClimbing()) return;
        if (player.isSwimming()) return;
        if (player.isInWater()) return;

        double dy = ny - s.lastY;
        long now = System.currentTimeMillis();

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("step");
        double minDy = sec != null ? sec.getDouble("min_dy", 0.95) : 0.95;
        double maxDy = sec != null ? sec.getDouble("max_dy", 1.10) : 1.10;
        long groundWindow = sec != null ? sec.getLong("from_ground_window_ms", FROM_GROUND_WINDOW_MS) : FROM_GROUND_WINDOW_MS;

        if (dy < minDy || dy > maxDy) return;

        if (!s.lastOnGround || (now - s.lastOnGroundMs) > groundWindow) return;

        if (s.lastDeltaY < -0.1) return;

        try {
            org.bukkit.block.Block below = player.getWorld().getBlockAt(
                (int) Math.floor(nx), (int) Math.floor(ny - 0.02), (int) Math.floor(nz));
            String name = below.getType().name();

            if (name.contains("BUBBLE_COLUMN") || name.contains("SCAFFOLDING")
                || name.contains("WATER") || name.contains("LAVA")
                || name.contains("HONEY_BLOCK") || name.contains("SLIME_BLOCK")) {
                return;
            }
        } catch (Throwable ignored) {
        }

        ViolationLevel lvl = (dy >= 1.00) ? ViolationLevel.HIGH : ViolationLevel.MID;
        sink.flag(new Violation(player, "step_packet",
            lvl,
            String.format("dy=%.3f from_ground_age=%dms", dy, now - s.lastOnGroundMs)));
    }
}
