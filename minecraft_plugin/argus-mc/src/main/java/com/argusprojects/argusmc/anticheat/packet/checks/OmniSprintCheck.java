package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Sprint omnidireccional: vanilla solo deja correr (sprint) apretando adelante. Corriendo en el piso
 * hacia atras o de costado (>100 grados respecto de la mirada) durante 8+ ticks es el hack.
 * En el piso la friccion mata la inercia en 2-3 ticks, asi que 8 ticks no son un giro con impulso.
 */
public final class OmniSprintCheck {

    private final ArgusPlugin plugin;

    public OmniSprintCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, double nx, double nz,
                                     boolean onGround, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("omnisprint")) return;
        double dx = nx - s.lastX, dz = nz - s.lastZ;
        if (Math.hypot(dx, dz) < 0.03) return;   // paquete sin movimiento (reenvio/idle): no cuenta ni corta la racha
        if (!s.packetSprinting || !onGround || !s.lastOnGround || Math.hypot(dx, dz) < 0.2
            || now - s.lastDamageTakenMs < 1_500L || now - s.serverVelAssignedAtMs < 1_500L || s.teleporting
            || player.isInsideVehicle() || player.isFlying() || player.isInWater()) {
            s.omniConsec = 0;
            return;
        }
        Material below = player.getLocation().clone().add(0, -0.2, 0).getBlock().getType();
        if (below.name().contains("ICE")) {
            s.omniConsec = 0;
            return;
        }
        if (angleToFacing(s.lastYaw, dx, dz) <= 100) {
            s.omniConsec = 0;
            return;
        }
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("omnisprint");
        int mid  = sec != null ? sec.getInt("ticks_mid", 8) : 8;
        int high = sec != null ? sec.getInt("ticks_high", 20) : 20;
        s.omniConsec++;
        if (s.omniConsec == mid || s.omniConsec == high) {
            sink.flag(new Violation(player, "omnisprint_packet",
                s.omniConsec >= high ? ViolationLevel.HIGH : ViolationLevel.MID,
                String.format("corre (sprint) hacia atras/costado %d ticks", s.omniConsec)));
        }
    }

    /** Angulo entre la direccion de movimiento y hacia donde mira (yaw Minecraft). */
    static double angleToFacing(float yawDeg, double dx, double dz) {
        double fx = -Math.sin(Math.toRadians(yawDeg)), fz = Math.cos(Math.toRadians(yawDeg));
        double len = Math.hypot(dx, dz);
        double dot = Math.max(-1, Math.min(1, (fx * dx + fz * dz) / len));
        return Math.toDegrees(Math.acos(dot));
    }
}
