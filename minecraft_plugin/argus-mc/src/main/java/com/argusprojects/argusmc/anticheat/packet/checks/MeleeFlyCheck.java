package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — MeleeFlyCheck.
 *
 * <p>Killaura es muy detectable cuando el player ataca mientras esta hovering
 * en el aire sin onGround, sin elytra, sin fall. Detectamos N attacks seguidos
 * con dy ~0 (hovering) y sin on-ground.
 *
 * <p>Whitelist: creative, spectator, elytra, in-vehicle, in water, jump-boost.
 */
public final class MeleeFlyCheck {

    private final ArgusPlugin plugin;

    public MeleeFlyCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player attacker, Entity target, PacketDataStore.State s,
                             long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("melee_fly")) return;
        if (target == null) return;
        GameMode gm = attacker.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) { s.meleeFlyConsec = 0; return; }
        if (attacker.isGliding() || attacker.isInsideVehicle() || attacker.isFlying()) {
            s.meleeFlyConsec = 0;
            return;
        }
        Material at = attacker.getLocation().getBlock().getType();
        if (at == Material.WATER || at == Material.LAVA
            || at == Material.LADDER || at == Material.VINE
            || at == Material.SCAFFOLDING) {
            s.meleeFlyConsec = 0;
            return;
        }

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("melee_fly");
        int consecMid  = sec != null ? sec.getInt("consec_mid", 4) : 4;
        int consecHigh = sec != null ? sec.getInt("consec_high", 8) : 8;
        double maxAbsDy= sec != null ? sec.getDouble("max_abs_dy", 0.08) : 0.08;

        boolean hovering = !s.lastOnGround
            && Math.abs(s.lastDeltaY) < maxAbsDy
            && attacker.getFallDistance() < 0.5f;

        if (!hovering) {
            s.meleeFlyConsec = 0;
            return;
        }

        s.meleeFlyConsec++;
        if (s.meleeFlyConsec >= consecHigh) {
            sink.flag(new Violation(attacker, "melee_fly_packet",
                ViolationLevel.HIGH,
                String.format("attacks hovering x%d (dy=%.3f fall=%.2f)",
                    s.meleeFlyConsec, s.lastDeltaY, attacker.getFallDistance())));
            s.meleeFlyConsec = 0;
        } else if (s.meleeFlyConsec >= consecMid) {
            sink.flag(new Violation(attacker, "melee_fly_packet",
                ViolationLevel.MID,
                String.format("attacks hovering x%d", s.meleeFlyConsec)));
        }
    }
}
