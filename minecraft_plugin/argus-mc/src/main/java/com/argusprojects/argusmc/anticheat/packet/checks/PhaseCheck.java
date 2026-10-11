package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class PhaseCheck {

    private final ArgusPlugin plugin;

    public PhaseCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("phase")) return;
        if (s.teleporting) return;
        if (player.getAllowFlight() && player.isFlying()) return;
        if (player.getGameMode() == org.bukkit.GameMode.SPECTATOR) return;
        if (player.getGameMode() == org.bukkit.GameMode.CREATIVE) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        double dx = nx - s.lastX;
        double dy = ny - s.lastY;
        double dz = nz - s.lastZ;
        double dist2 = dx * dx + dy * dy + dz * dz;

        if (dist2 < 1.0) return;

        if (dist2 > 144.0) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("phase");
        int minBlockedSamples = sec != null ? sec.getInt("min_blocked_samples", 2) : 2;
        int samplesPerBlock   = sec != null ? sec.getInt("samples_per_block",   2) : 2;

        int steps = Math.max(2, (int) Math.ceil(Math.sqrt(dist2) * samplesPerBlock));
        org.bukkit.World w = player.getWorld();
        int blockedSteps = 0;
        for (int i = 1; i < steps; i++) {
            double t = (double) i / steps;
            double sx = s.lastX + dx * t;
            double sy = s.lastY + dy * t + 1.0;
            double sz = s.lastZ + dz * t;
            Material m = w.getBlockAt((int) Math.floor(sx), (int) Math.floor(sy), (int) Math.floor(sz)).getType();
            if (isHardSolid(m)) blockedSteps++;
        }

        if (blockedSteps >= minBlockedSamples) {
            sink.flag(new Violation(player, "phase_packet",
                ViolationLevel.HIGH,
                String.format("dx=%.2f dy=%.2f dz=%.2f blockedSamples=%d/%d", dx, dy, dz, blockedSteps, steps - 1)));
        }
    }

    private static boolean isHardSolid(Material m) {
        if (m == null || m.isAir()) return false;
        switch (m) {
            case STONE: case DEEPSLATE: case COBBLESTONE: case BEDROCK: case OBSIDIAN:
            case OAK_PLANKS: case BIRCH_PLANKS: case SPRUCE_PLANKS: case JUNGLE_PLANKS:
            case ACACIA_PLANKS: case DARK_OAK_PLANKS: case CHERRY_PLANKS: case CRIMSON_PLANKS: case WARPED_PLANKS:
            case WHITE_WOOL: case BLACK_WOOL: case GRAY_WOOL: case RED_WOOL: case GREEN_WOOL:
            case BLUE_WOOL: case YELLOW_WOOL: case ORANGE_WOOL: case PURPLE_WOOL: case PINK_WOOL:
            case BROWN_WOOL: case CYAN_WOOL: case LIGHT_BLUE_WOOL: case LIGHT_GRAY_WOOL:
            case LIME_WOOL: case MAGENTA_WOOL:
            case IRON_BLOCK: case GOLD_BLOCK: case DIAMOND_BLOCK: case NETHERITE_BLOCK:
            case COAL_BLOCK: case EMERALD_BLOCK: case LAPIS_BLOCK: case REDSTONE_BLOCK:
                return true;
            default:
                return false;
        }
    }
}
