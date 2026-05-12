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
import org.bukkit.potion.PotionEffectType;

/**
 * Pack 48 round2 — JetpackCheck.
 *
 * <p>Jetpack es un cheat que mantiene deltaY positivo constante (subiendo
 * suave) sin elytra, jump-boost ni climable. El nombre viene de Vape/Wurst.
 *
 * <p>Heuristica: si dyConsec contadores indican N packets con dy &gt; threshold
 * SOSTENIDO, y el jugador no es creative/spectator, no esta volando legitimo
 * (allow_flight + flying), no usa elytra (gliding), no tiene jump boost
 * relevante, no esta nadando en agua/lava, no esta en climbable — flag.
 */
public final class JetpackCheck {

    private final ArgusPlugin plugin;

    public JetpackCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("jetpack")) return;
        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) {
            s.jetpackConsec = 0;
            return;
        }
        if (player.getAllowFlight() && player.isFlying()) { s.jetpackConsec = 0; return; }
        if (player.isGliding()) { s.jetpackConsec = 0; return; }
        if (player.isInsideVehicle()) { s.jetpackConsec = 0; return; }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("jetpack");
        double minDy = sec != null ? sec.getDouble("min_dy", 0.18) : 0.18;
        int    consecMid = sec != null ? sec.getInt("consec_mid", 4) : 4;
        int    consecHigh= sec != null ? sec.getInt("consec_high", 7) : 7;

        // Permitido si esta en agua, climbable o jump-boosted relevante.
        Material at = player.getLocation().getBlock().getType();
        if (at == Material.WATER || at == Material.LAVA
            || at == Material.LADDER || at == Material.VINE
            || at == Material.SCAFFOLDING) {
            s.jetpackConsec = 0;
            return;
        }
        if (hasJumpBoost(player) >= 3) {
            s.jetpackConsec = 0;
            return;
        }

        double dy = ny - s.lastY;
        if (dy >= minDy && !s.lastOnGround) {
            s.jetpackConsec++;
            if (s.jetpackConsec >= consecHigh) {
                sink.flag(new Violation(player, "jetpack_packet",
                    ViolationLevel.HIGH,
                    String.format("dy>%.2f x%d", minDy, s.jetpackConsec)));
                s.jetpackConsec = 0;
            } else if (s.jetpackConsec >= consecMid) {
                sink.flag(new Violation(player, "jetpack_packet",
                    ViolationLevel.MID,
                    String.format("dy>%.2f x%d", minDy, s.jetpackConsec)));
            }
        } else {
            // Si baja o se queda quieto, reset.
            if (dy <= 0) s.jetpackConsec = 0;
        }
    }

    private int hasJumpBoost(Player p) {
        try {
            var t = PotionEffectType.getByName("JUMP_BOOST");
            if (t == null) t = PotionEffectType.getByName("JUMP");
            if (t != null && p.hasPotionEffect(t)) {
                var pe = p.getPotionEffect(t);
                if (pe != null) return pe.getAmplifier();
            }
        } catch (Throwable ignored) {}
        return -1;
    }
}
