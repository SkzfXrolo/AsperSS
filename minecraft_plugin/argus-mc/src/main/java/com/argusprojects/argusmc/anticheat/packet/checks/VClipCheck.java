package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

public final class VClipCheck {

    private final ArgusPlugin plugin;

    public VClipCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("vclip")) return;
        if (plugin.getLagCompensator().shouldSuppress(player, "vclip")) return;
        if (s.teleporting) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.getAllowFlight() && player.isFlying()) return;
        if (player.isInsideVehicle()) return;
        if (player.isGliding()) return;
        if (player.isSwimming()) return;
        if (hasEffect(player, "LEVITATION")) return;
        if (hasEffect(player, "SLOW_FALLING")) return;

        double dy = ny - s.lastY;
        s.lastDeltaY = dy;

        if (dy <= 0.6) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("vclip");
        double midThreshold      = sec != null ? sec.getDouble("dy_mid",  0.65) : 0.65;
        double highThreshold     = sec != null ? sec.getDouble("dy_high", 1.20) : 1.20;
        double criticalThreshold = sec != null ? sec.getDouble("dy_critical", 2.00) : 2.00;

        double allowance = jumpBoostAllowance(player);

        double adjustedMid      = midThreshold      + allowance;
        double adjustedHigh     = highThreshold     + allowance;
        double adjustedCritical = criticalThreshold + allowance;

        if (dy >= adjustedCritical) {
            sink.flag(new Violation(player, "vclip_packet",
                ViolationLevel.CRITICAL,
                String.format("dy=%.3f (>=%.2f, jb_allow=%.2f)", dy, adjustedCritical, allowance)));
        } else if (dy >= adjustedHigh) {
            sink.flag(new Violation(player, "vclip_packet",
                ViolationLevel.HIGH,
                String.format("dy=%.3f (>=%.2f, jb_allow=%.2f)", dy, adjustedHigh, allowance)));
        } else if (dy >= adjustedMid) {
            sink.flag(new Violation(player, "vclip_packet",
                ViolationLevel.MID,
                String.format("dy=%.3f (>=%.2f, jb_allow=%.2f)", dy, adjustedMid, allowance)));
        }
    }

    @SuppressWarnings("deprecation")
    private static double jumpBoostAllowance(Player p) {
        try {
            PotionEffectType type = PotionEffectType.getByName("JUMP_BOOST");
            if (type == null) type = PotionEffectType.getByName("JUMP");
            if (type == null) return 0.0;
            PotionEffect ef = p.getPotionEffect(type);
            if (ef == null) return 0.0;
            return 0.10 * (ef.getAmplifier() + 1);
        } catch (Throwable t) {
            return 0.0;
        }
    }

    @SuppressWarnings("deprecation")
    private static boolean hasEffect(Player p, String name) {
        try {
            PotionEffectType type = PotionEffectType.getByName(name);
            return type != null && p.hasPotionEffect(type);
        } catch (Throwable t) {
            return false;
        }
    }
}
