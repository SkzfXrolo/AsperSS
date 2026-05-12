package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.util.Vector;

/**
 * Pack 47 — Reach packet-based.
 *
 * <p>El check de reach Bukkit-based usa la posicion del attacker en el momento
 * de {@code EntityDamageByEntityEvent}, que ya pasó por compensaciones del
 * server. Aca usamos la posicion EXACTA del attacker en el tick del packet
 * de ataque (s.lastX/Y/Z, actualizado por el listener antes que llegue el
 * InteractEntity).
 *
 * <p>Limites vanilla:
 * <ul>
 *   <li>Survival 1.8: 3.0 bloques de reach (caja de hitbox + tolerancia)</li>
 *   <li>Survival 1.9+: 3.0 bloques tambien</li>
 *   <li>Creative: 5.0 bloques</li>
 * </ul>
 *
 * <p>Toleramos 3.4 / 5.4 para cubrir lag + hitbox interpolation. &gt; 3.6 sostenido
 * en survival = HIGH; &gt; 4.5 = CRITICAL.
 */
public final class ReachPacketCheck {

    private final ArgusPlugin plugin;

    public ReachPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleAttack(Player player, Entity target,
                             PacketDataStore.State s,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("reach_packet")) return;
        if (target == null) return;
        if (target.getUniqueId().equals(player.getUniqueId())) return;

        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE) {
            return; // 5.0 vanilla — no nos preocupa
        }
        if (gm == GameMode.SPECTATOR) return;

        // Posicion del attacker en el tick del packet — desde el datastore.
        // Eye location: y + 1.62 (1.8) / y + 1.5 (sneaking). Asumimos 1.62.
        double ax = s.lastX;
        double ay = s.lastY + 1.62;
        double az = s.lastZ;
        Vector eye = new Vector(ax, ay, az);

        // Posicion del target — la hitbox del target ya esta corregida por el server.
        Vector tHead = target.getLocation().toVector().add(new Vector(0, target.getHeight() * 0.5, 0));

        double dist = eye.distance(tHead);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("reach_packet");
        double midThr      = sec != null ? sec.getDouble("dist_mid",      3.3) : 3.3;
        double highThr     = sec != null ? sec.getDouble("dist_high",     3.6) : 3.6;
        double criticalThr = sec != null ? sec.getDouble("dist_critical", 4.5) : 4.5;

        if (dist > criticalThr) {
            sink.flag(new Violation(player, "reach_packet",
                ViolationLevel.CRITICAL,
                String.format("dist=%.2f target=%s", dist, target.getType().name().toLowerCase())));
        } else if (dist > highThr) {
            sink.flag(new Violation(player, "reach_packet",
                ViolationLevel.HIGH,
                String.format("dist=%.2f target=%s", dist, target.getType().name().toLowerCase())));
        } else if (dist > midThr) {
            sink.flag(new Violation(player, "reach_packet",
                ViolationLevel.MID,
                String.format("dist=%.2f target=%s", dist, target.getType().name().toLowerCase())));
        }
    }
}
