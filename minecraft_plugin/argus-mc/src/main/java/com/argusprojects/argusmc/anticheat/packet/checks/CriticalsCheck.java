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
 * Criticals (packet): antes de pegar manda un "mini salto" falso (sube 0.06-0.3 y queda en el aire)
 * para que el server cuente el golpe como critico. En vanilla, despegar del piso sube 0.42 de una
 * (menos solo con techo encima, rebote en slime/cama o knockback): despegar con una subida chica
 * pegado a un ataque es la firma.
 */
public final class CriticalsCheck {

    private static final double VANILLA_JUMP = 0.42;

    private final ArgusPlugin plugin;

    public CriticalsCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s, double nx, double ny, double nz,
                                     boolean onGround, long now) {
        double dy = ny - s.lastY;
        if (!s.lastOnGround || onGround || !isMicroHop(dy)) return;
        if (now - s.lastDamageTakenMs < 1_000L) return;
        if (player.isFlying() || player.isInsideVehicle() || player.isInWater() || player.isClimbing()) return;
        World w = player.getWorld();
        Material below = type(w, s.lastX, s.lastY - 0.2, s.lastZ);
        if (below == Material.SLIME_BLOCK || below == Material.HONEY_BLOCK || below.name().endsWith("_BED")) return;
        if (type(w, nx, s.lastY + 2.2, nz).isSolid()) return; // techo bajo: el salto queda corto
        Material at = type(w, nx, ny, nz);
        if (at == Material.POWDER_SNOW || at == Material.SCAFFOLDING || at == Material.BUBBLE_COLUMN) return;
        s.critHopMs = now;
    }

    public void handleAttack(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("criticals")) return;
        if (now - s.critHopMs > 150L) return;
        s.critHopMs = 0L;
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("criticals");
        long window = sec != null ? sec.getLong("window_ms", 10_000L) : 10_000L;
        int mid  = sec != null ? sec.getInt("hits_mid", 3) : 3;
        int high = sec != null ? sec.getInt("hits_high", 6) : 6;
        if (now - s.critWindowStartMs > window) {
            s.critWindowStartMs = now;
            s.critHits = 0;
        }
        s.critHits++;
        if (s.critHits >= mid) {
            ViolationLevel lvl = s.critHits >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "criticals_packet", lvl,
                String.format("mini-salto falso antes de pegar x%d", s.critHits)));
            if (lvl == ViolationLevel.HIGH) s.critHits = 0;
        }
    }

    static boolean isMicroHop(double dy) {
        return dy > 0.0001 && dy < VANILLA_JUMP - 0.02;
    }

    private static Material type(World w, double x, double y, double z) {
        return w.getBlockAt(NumberConversions.floor(x), NumberConversions.floor(y), NumberConversions.floor(z)).getType();
    }
}
