package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.MovementContext;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.enchantments.Enchantment;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

public final class NoSlowSneakCheck {

    private static final long SNEAK_SETTLE_MS = 400L;
    private static final long DAMAGE_GRACE_MS = 1000L;

    private final ArgusPlugin plugin;

    public NoSlowSneakCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double nz, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("noslowsneak")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "noslowsneak")) return;
        if (plugin.getWarmupGracePeriod().inGrace(player, "noslowsneak")) return;
        // En el aire se conserva la inercia (sprint-jump + shift es legit) y al agacharse la
        // velocidad tarda unos ticks en caer: solo se evalua en piso con sneak sostenido.
        if (!s.sneakActive || !s.lastOnGround || now - s.sneakStartMs < SNEAK_SETTLE_MS
            || now - s.lastDamageTakenMs < DAMAGE_GRACE_MS) {
            resetWindow(s, now);
            s.noSlowSneakConsec = 0;
            return;
        }
        MovementContext ctx = MovementContext.snapshotAt(player, nx, s.lastY, nz);
        if (ctx.onIce || ctx.isLegitFlightLike()) {
            resetWindow(s, now);
            s.noSlowSneakConsec = 0;
            return;
        }
        // Promedio por ventanas de 1s: la velocidad de un solo paquete depende de cuando llega
        // (con tunel/wifi dos paquetes juntos dan picos falsos).
        if (s.noSlowSneakWinStartMs == 0L) resetWindow(s, now);
        s.noSlowSneakWinDist += Math.hypot(nx - s.lastX, nz - s.lastZ);
        long span = now - s.noSlowSneakWinStartMs;
        if (span < 1_000L) return;
        double bps = s.noSlowSneakWinDist * 1000.0 / span;
        resetWindow(s, now);

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("noslowsneak");
        // Agachado = 0.3 de caminar (1.31 bps); en 1.8 el sprint sigue activo al agacharse (x1.3 = 1.7).
        // Swift Sneak suma 0.15 por nivel.
        double sneakFactor = (0.3 + 0.15 * swiftSneakLevel(player)) / 0.3;
        double maxBps = (sec != null ? sec.getDouble("max_sneak_bps", 1.95) : 1.95)
            * sneakFactor * Math.max(1.0, ctx.horizontalSpeedMultiplier());
        int consecMid  = sec != null ? sec.getInt("consec_mid", 2) : 2;
        int consecHigh = sec != null ? sec.getInt("consec_high", 4) : 4;

        if (bps > maxBps) {
            s.noSlowSneakConsec++;
            if (s.noSlowSneakConsec >= consecHigh) {
                sink.flag(new Violation(player, "noslowsneak_packet", ViolationLevel.HIGH,
                    String.format("agachado a %.2f b/s (max %.2f) %ds seguidos", bps, maxBps, s.noSlowSneakConsec)));
                s.noSlowSneakConsec = 0;
            } else if (s.noSlowSneakConsec >= consecMid) {
                sink.flag(new Violation(player, "noslowsneak_packet", ViolationLevel.MID,
                    String.format("agachado a %.2f b/s (max %.2f) %ds seguidos", bps, maxBps, s.noSlowSneakConsec)));
            }
        } else {
            s.noSlowSneakConsec = 0;
        }
    }

    private static void resetWindow(PacketDataStore.State s, long now) {
        s.noSlowSneakWinStartMs = now;
        s.noSlowSneakWinDist = 0;
        s.noSlowSneakLastMs = now;
    }

    private static int swiftSneakLevel(Player p) {
        try {
            ItemStack legs = p.getInventory().getLeggings();
            return legs == null ? 0 : legs.getEnchantmentLevel(Enchantment.SWIFT_SNEAK);
        } catch (Throwable t) {
            return 0;
        }
    }
}
