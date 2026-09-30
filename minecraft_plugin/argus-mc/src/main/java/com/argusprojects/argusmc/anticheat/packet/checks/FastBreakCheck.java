package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

public final class FastBreakCheck {

    private final ArgusPlugin plugin;

    public FastBreakCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleStartDigging(Player player, PacketDataStore.State s, long now,
                                   Material blockType) {
        if (player.getGameMode() == GameMode.CREATIVE) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;
        s.currentBreakStartMs = now;
        s.currentBreakBlockMaterial = blockType != null ? blockType.name() : null;
    }

    public void handleFinishDigging(Player player, PacketDataStore.State s, long now,
                                    Material blockType, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("fast_break")) return;
        if (player.getGameMode() == GameMode.CREATIVE) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;
        if (blockType == null) return;
        if (blockType.isAir()) return;

        float hardness;
        try {
            hardness = blockType.getHardness();
        } catch (Throwable t) {
            return;
        }

        if (hardness < 0.05f) return;

        s.pushBreak(now);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fast_break");
        long minMsHardBlock = sec != null ? sec.getLong("min_ms_hard",     80L)  : 80L;
        long minMsVeryHard  = sec != null ? sec.getLong("min_ms_very_hard", 200L) : 200L;
        float hardThresh    = sec != null ? (float) sec.getDouble("hardness_threshold",      1.5)  : 1.5f;
        float veryHardThresh= sec != null ? (float) sec.getDouble("hardness_threshold_very", 3.0)  : 3.0f;

        if (s.currentBreakStartMs == 0L) {

            sink.flag(new Violation(player, "fast_break_packet",
                ViolationLevel.HIGH,
                String.format("no-start-digging, hardness=%.2f block=%s", hardness, blockType.name())));
            s.currentBreakStartMs = 0L;
            s.currentBreakBlockMaterial = null;
            return;
        }

        long elapsed = now - s.currentBreakStartMs;
        s.currentBreakStartMs = 0L;
        s.currentBreakBlockMaterial = null;

        if (elapsed < 0L) return;

        if (hardness >= veryHardThresh && elapsed < minMsVeryHard) {
            sink.flag(new Violation(player, "fast_break_packet",
                ViolationLevel.HIGH,
                String.format("elapsed=%dms hardness=%.2f block=%s (very-hard threshold=%dms)",
                    elapsed, hardness, blockType.name(), minMsVeryHard)));
            return;
        }
        if (hardness >= hardThresh && elapsed < minMsHardBlock) {
            sink.flag(new Violation(player, "fast_break_packet",
                ViolationLevel.HIGH,
                String.format("elapsed=%dms hardness=%.2f block=%s (hard threshold=%dms)",
                    elapsed, hardness, blockType.name(), minMsHardBlock)));
        }
    }
}
