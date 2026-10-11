package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.World;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * AirPlace: coloca "contra" un bloque que en el server es aire. El raytrace del cliente vanilla
 * nunca apunta al aire, asi que el paquete de colocacion siempre referencia un bloque real.
 * Se tolera un bloque recien roto (el cliente todavia lo ve) y se cuenta en ventana.
 */
public final class AirPlaceCheck {

    private final ArgusPlugin plugin;

    public AirPlaceCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePlacement(Player player, PacketDataStore.State s, int x, int y, int z, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("airplace")) return;
        if (player.getGameMode() == GameMode.SPECTATOR) return;
        World w = player.getWorld();
        if (y < w.getMinHeight() || y >= w.getMaxHeight()) return;   // 1.8 "click al aire" (-1,-1,-1)
        if (now - s.lastDigMs < 600L) return;                          // bloque recien roto
        if (!w.getBlockAt(x, y, z).getType().isAir()) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("airplace");
        long window = sec != null ? sec.getLong("window_ms", 10_000L) : 10_000L;
        int mid  = sec != null ? sec.getInt("hits_mid", 3) : 3;
        int high = sec != null ? sec.getInt("hits_high", 6) : 6;
        if (now - s.airPlaceWindowStartMs > window) {
            s.airPlaceWindowStartMs = now;
            s.airPlaceHits = 0;
        }
        s.airPlaceHits++;
        if (s.airPlaceHits >= mid) {
            ViolationLevel lvl = s.airPlaceHits >= high ? ViolationLevel.HIGH : ViolationLevel.MID;
            sink.flag(new Violation(player, "airplace_packet", lvl,
                String.format("coloca contra aire en (%d,%d,%d) x%d", x, y, z, s.airPlaceHits)));
            if (lvl == ViolationLevel.HIGH) s.airPlaceHits = 0;
        }
    }
}
