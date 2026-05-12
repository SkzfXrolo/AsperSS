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

/**
 * Pack 48 #486 — FastBreakCheck (mining speed vs tool/enchant).
 *
 * <p>Mide el intervalo entre {@code START_DIGGING} y {@code FINISHED_DIGGING}
 * y lo compara con el minimo plausible para el bloque y la herramienta del
 * jugador. Como el calculo exacto de break-time vanilla requiere el sistema
 * completo de hardness/efficiency/haste/aqua-affinity, esta check usa un
 * piso conservador:
 *
 * <ul>
 *   <li>Cualquier bloque {@code hardness >= 1.5} (stone, ores) roto en
 *       &lt; 80ms = HIGH, casi imposible incluso con netherite + eff V.</li>
 *   <li>Bloque {@code hardness >= 3.0} (obsidian, etc) roto en &lt; 200ms = HIGH.</li>
 *   <li>FINISHED_DIGGING sin START_DIGGING previo (insta-break sin warmup)
 *       en un bloque {@code hardness > 0.05} = HIGH (clasico FastBreak hack).</li>
 * </ul>
 *
 * <p>Skip total en creative y spectator.
 */
public final class FastBreakCheck {

    private final ArgusPlugin plugin;

    public FastBreakCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** Inicio de minado: solo registramos el tiempo y el bloque. */
    public void handleStartDigging(Player player, PacketDataStore.State s, long now,
                                   Material blockType) {
        if (player.getGameMode() == GameMode.CREATIVE) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;
        s.currentBreakStartMs = now;
        s.currentBreakBlockMaterial = blockType != null ? blockType.name() : null;
    }

    /** Fin de minado: aca decidimos si es FastBreak. */
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
        // Bloques instant-break (1-tick) — skip.
        if (hardness < 0.05f) return;

        s.pushBreak(now);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fast_break");
        long minMsHardBlock = sec != null ? sec.getLong("min_ms_hard",     80L)  : 80L;
        long minMsVeryHard  = sec != null ? sec.getLong("min_ms_very_hard", 200L) : 200L;
        float hardThresh    = sec != null ? (float) sec.getDouble("hardness_threshold",      1.5)  : 1.5f;
        float veryHardThresh= sec != null ? (float) sec.getDouble("hardness_threshold_very", 3.0)  : 3.0f;

        if (s.currentBreakStartMs == 0L) {
            // FINISH sin START previo — insta-break sin warmup.
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
