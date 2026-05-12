package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 #485 — FastPlaceCheck (Scaffold / FastPlace).
 *
 * <p>Mide BlockPlacement packets dentro de una ventana corta. Vanilla cap
 * teorico al hacer right-click sostenido es ~5 placements/segundo (un placement
 * por tick). Scaffold hacks subiendo verticalmente generan 10-20+ placements/s.
 *
 * <p>Como PLAYER_BLOCK_PLACEMENT tambien dispara para clicks con item (no solo
 * bloques — bow, comer, etc.), este check tiene un threshold conservador para
 * no falsear con jugadores que estan derecho-clickeando legitimamente con bow
 * o food. Solo flagea por encima del cap real de placements vanilla.
 *
 * <p>Skip en creative (placement instantaneo legitimo).
 */
public final class FastPlaceCheck {

    private final ArgusPlugin plugin;

    public FastPlaceCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** Llamado por el listener cada vez que llega un PLAYER_BLOCK_PLACEMENT. */
    public void handleBlockPlacement(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("fast_place")) return;
        if (player.getGameMode() == GameMode.CREATIVE) return;

        s.pushPlace(now);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("fast_place");
        int maxPerSec  = sec != null ? sec.getInt("max_per_sec",  9)  : 9;
        int maxPerSec2 = sec != null ? sec.getInt("max_per_sec2", 14) : 14;
        int maxPerSec3 = sec != null ? sec.getInt("max_per_sec3", 22) : 22;

        int recent = s.recentPlacesWithin(1_000L, now);
        if (recent >= maxPerSec3) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.HIGH,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec3)));
        } else if (recent >= maxPerSec2) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.MID,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec2)));
        } else if (recent >= maxPerSec) {
            sink.flag(new Violation(player, "fast_place_packet",
                ViolationLevel.LOW,
                String.format("places/sec=%d (>=%d)", recent, maxPerSec)));
        }
    }
}
