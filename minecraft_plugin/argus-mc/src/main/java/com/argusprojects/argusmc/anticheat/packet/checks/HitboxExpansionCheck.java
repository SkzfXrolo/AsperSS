package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Location;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.util.BoundingBox;

/**
 * Pack 48 round2 — HitboxExpansionCheck.
 *
 * <p>Detecta hits que provienen de un punto fuera del hitbox normal +
 * margen del target. Es el "HitboxExpander" / "Reach via expandHitbox"
 * que infla el bounding box client-side para registrar hits laterales.
 *
 * <p>Calcula la distancia minima del eye-vector del attacker al bounding
 * box del target. Si esa distancia es &gt; ~0.10 (margen vanilla), el
 * hit deberia haber fallado en vanilla — el cheat lo "infla".
 */
public final class HitboxExpansionCheck {

    private final ArgusPlugin plugin;

    public HitboxExpansionCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player attacker, Entity target, PacketDataStore.State s,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("hitbox_expansion")) return;
        if (target == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("hitbox_expansion");
        double margin       = sec != null ? sec.getDouble("max_margin", 0.20) : 0.20;
        double extremeMargin= sec != null ? sec.getDouble("extreme_margin", 0.50) : 0.50;

        Location eye = attacker.getEyeLocation();
        BoundingBox bb;
        try {
            bb = target.getBoundingBox();
        } catch (Throwable t) {
            return; // API antigua
        }

        // Calculo manual de distancia minima al AABB.
        double cx = clamp(eye.getX(), bb.getMinX(), bb.getMaxX());
        double cy = clamp(eye.getY(), bb.getMinY(), bb.getMaxY());
        double cz = clamp(eye.getZ(), bb.getMinZ(), bb.getMaxZ());
        double dx = eye.getX() - cx;
        double dy = eye.getY() - cy;
        double dz = eye.getZ() - cz;
        // Distancia 3D al punto mas cercano del AABB.
        double distToBox = Math.sqrt(dx * dx + dy * dy + dz * dz);

        // Lo medimos vs el reach maximo "esperable" y le restamos. Lo que sobra
        // es el "margen" de hitbox expansion. Si margen > umbral, flagea.
        // (no chequeamos reach absoluto — eso lo hace ReachPacketCheck.)
        double reachMax = 3.0;
        double overflow = distToBox - reachMax;
        if (overflow >= extremeMargin) {
            sink.flag(new Violation(attacker, "hitbox_expansion_packet",
                ViolationLevel.HIGH,
                String.format("dist_bb=%.2f overflow=%.2f", distToBox, overflow)));
        } else if (overflow >= margin) {
            sink.flag(new Violation(attacker, "hitbox_expansion_packet",
                ViolationLevel.MID,
                String.format("dist_bb=%.2f overflow=%.2f", distToBox, overflow)));
        }
    }

    private static double clamp(double v, double min, double max) {
        return Math.max(min, Math.min(max, v));
    }
}
