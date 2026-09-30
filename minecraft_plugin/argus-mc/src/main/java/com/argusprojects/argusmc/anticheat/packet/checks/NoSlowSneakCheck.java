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
        if (!s.sneakActive || now - s.lastDamageTakenMs < DAMAGE_GRACE_MS) {
            s.noSlowSneakConsec = 0;
            s.noSlowSneakLastMs = now;
            return;
        }
        MovementContext ctx = MovementContext.snapshotAt(player, nx, s.lastY, nz);
        if (ctx.onIce || ctx.isLegitFlightLike()) {
            s.noSlowSneakConsec = 0;
            s.noSlowSneakLastMs = now;
            return;
        }
        long dt = now - s.noSlowSneakLastMs;
        s.noSlowSneakLastMs = now;
        if (dt < 30L || dt > 500L) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("noslowsneak");
        // Vanilla agachado = 0.3 de la velocidad normal; Swift Sneak suma 0.15 por nivel.
        double sneakFactor = (0.3 + 0.15 * swiftSneakLevel(player)) / 0.3;
        double maxBps = (sec != null ? sec.getDouble("max_sneak_bps", 1.5) : 1.5)
            * sneakFactor * Math.max(1.0, ctx.horizontalSpeedMultiplier());
        int consecMid = sec != null ? sec.getInt("consec_mid", 5) : 5;
        int consecHigh= sec != null ? sec.getInt("consec_high", 10) : 10;

        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double bps = Math.sqrt(dx*dx + dz*dz) * 1000.0 / dt;

        if (bps > maxBps) {
            s.noSlowSneakConsec++;
            if (s.noSlowSneakConsec >= consecHigh) {
                sink.flag(new Violation(player, "noslowsneak_packet",
                    ViolationLevel.HIGH,
                    String.format("sneak bps=%.2f > %.2f x%d", bps, maxBps, s.noSlowSneakConsec)));
                s.noSlowSneakConsec = 0;
            } else if (s.noSlowSneakConsec >= consecMid) {
                sink.flag(new Violation(player, "noslowsneak_packet",
                    ViolationLevel.MID,
                    String.format("sneak bps=%.2f x%d", bps, s.noSlowSneakConsec)));
            }
        } else {
            s.noSlowSneakConsec = 0;
        }
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
