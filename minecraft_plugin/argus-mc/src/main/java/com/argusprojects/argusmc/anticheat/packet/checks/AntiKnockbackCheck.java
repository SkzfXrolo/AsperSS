package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.util.NumberConversions;

/**
 * AntiKB: el server manda un knockback y el cliente no lo aplica.
 * Se mide cuanto se movio el jugador EN LA DIRECCION del knockback (no el modulo: si venia
 * corriendo, su propio movimiento no cuenta como haberlo recibido) y si subio el salto vertical,
 * a lo largo de toda la ventana ping + margen, porque el primer paquete tras el golpe suele ser
 * anterior a que el cliente reciba la velocidad.
 */
public final class AntiKnockbackCheck {

    /** Aceleracion maxima por input en un tick (sprint en piso); puede ir en contra del knockback. */
    private static final double MAX_INPUT_ACCEL = 0.13;

    private final ArgusPlugin plugin;

    public AntiKnockbackCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz, long now, ViolationSink sink) {
        if (plugin.getLagCompensator().shouldSuppress(player, "antikb")
            || plugin.getWarmupGracePeriod().inGrace(player, "antikb")) {
            s.kbPending = false;
            return;
        }
        if (!s.kbPending) return;
        if (!plugin.getAnticheatConfig().isCheckEnabled("antikb")) {
            s.kbPending = false;
            return;
        }
        double kh = Math.hypot(s.kbX, s.kbZ);
        if (kh > 1e-6) {
            double along = ((nx - s.lastX) * s.kbX + (nz - s.lastZ) * s.kbZ) / kh;
            s.kbBestAlong = Math.max(s.kbBestAlong, along);
        }
        s.kbBestDy = Math.max(s.kbBestDy, ny - s.lastY);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("antikb");
        long margin = sec != null ? sec.getLong("window_margin_ms", 400L) : 400L;
        if (now - s.kbAtMs < Math.min(1_500L, s.pingMs + margin)) return;
        s.kbPending = false;

        if (player.isFlying() || player.isInsideVehicle() || player.isInWater() || player.isClimbing()
            || player.isGliding() || s.teleporting) return;
        Material at = player.getLocation().getBlock().getType();
        if (at == Material.COBWEB || at == Material.POWDER_SNOW || at == Material.LAVA) return;

        boolean horizIgnored = kh >= 0.2 && s.kbBestAlong < kh * 0.35 - MAX_INPUT_ACCEL * 0.5
            && !blockedAlong(player.getWorld(), s.lastX, s.lastY, s.lastZ, s.kbX / kh, s.kbZ / kh);
        boolean vertIgnored = s.kbY >= 0.25 && s.kbBestDy < s.kbY * 0.4
            && !solid(player.getWorld(), s.lastX, s.lastY + 2.1, s.lastZ);
        if (!(horizIgnored && (vertIgnored || s.kbY < 0.25))) return;

        long window = sec != null ? sec.getLong("window_ms", 10_000L) : 10_000L;
        int mid  = sec != null ? sec.getInt("ignored_mid", 2) : 2;
        int high = sec != null ? sec.getInt("ignored_high", 4) : 4;
        if (now - s.antiKbWindowStartMs > window) {
            s.antiKbWindowStartMs = now;
            s.antiKbConsec = 0;
        }
        s.antiKbConsec++;
        if (s.antiKbConsec >= mid) {
            ViolationLevel lvl = s.antiKbConsec >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "antikb_packet", lvl,
                String.format("ignora knockback x%d (esperado %.2f, se movio %.2f hacia atras, subio %.2f/%.2f)",
                    s.antiKbConsec, kh, s.kbBestAlong, s.kbBestDy, s.kbY)));
            if (lvl == ViolationLevel.HIGH) s.antiKbConsec = 0;
        }
    }

    /** Pared detras: el knockback choca y no hay desplazamiento, no es cheat. */
    private static boolean blockedAlong(World w, double x, double y, double z, double ux, double uz) {
        double tx = x + ux * 0.5, tz = z + uz * 0.5;
        return solid(w, tx, y + 0.1, tz) || solid(w, tx, y + 1.1, tz);
    }

    private static boolean solid(World w, double x, double y, double z) {
        return w.getBlockAt(NumberConversions.floor(x), NumberConversions.floor(y), NumberConversions.floor(z))
            .getType().isSolid();
    }
}
