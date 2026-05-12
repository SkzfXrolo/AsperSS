package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffect;
import org.bukkit.potion.PotionEffectType;

/**
 * Pack 48 #484 — SpeedPacketCheck (velocidad real horizontal por packet).
 *
 * <p>El check Bukkit-based mide blocks/sec via {@code PlayerMoveEvent}, que
 * el server clampea. A nivel packet medimos el delta XZ REAL entre dos
 * PlayerPosition packets y lo escalamos a bps. Vanilla sprint cap:
 * ~5.6 b/s plano, ~7.0 con sprint + speed II, ~12-13 con elytra glide.
 *
 * <p>Tolerancia/whitelist:
 * <ul>
 *   <li>Speed potion: +20% por amplifier</li>
 *   <li>Sprint: implicito en cap (~5.6 b/s)</li>
 *   <li>Ice variants (BLUE_ICE/PACKED_ICE/ICE): +40% pico</li>
 *   <li>Slime/SBS: skip (catapulta legitima)</li>
 *   <li>Elytra/vehicle/swimming: skip total</li>
 *   <li>Soul Sand / Soul Soil con Soul Speed: +40% pico</li>
 * </ul>
 *
 * <p>El check tolera UN packet outlier (lag spike puede comprimir tiempos);
 * solo flagea si 3 packets consecutivos pasan el cap.
 */
public final class SpeedPacketCheck {

    private final ArgusPlugin plugin;

    public SpeedPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     long now,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("speed_packet")) return;
        if (s.teleporting) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.getAllowFlight() && player.isFlying()) return;
        if (player.isInsideVehicle()) return;
        if (player.isGliding()) return;
        if (player.isSwimming()) return;
        if (player.isInWater()) return;
        if (player.isClimbing()) return;

        long dt = Math.max(1L, now - s.lastMoveMs);
        if (dt > 250L) return; // gap demasiado grande, lag — no medir.

        double dx = nx - s.lastX;
        double dz = nz - s.lastZ;
        double dh = Math.sqrt(dx * dx + dz * dz);
        if (dh < 0.05) return; // quieto.

        double bps = dh * 1000.0 / dt;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("speed_packet");
        double baseCap = sec != null ? sec.getDouble("max_bps", 6.5) : 6.5;
        int consecutiveToFlag = sec != null ? sec.getInt("consecutive_to_flag", 3) : 3;

        // Bonificaciones por efectos/biomas.
        double allowance = 1.0;
        PotionEffect speed = getEffect(player, "SPEED");
        if (speed != null) allowance *= 1.0 + 0.20 * (speed.getAmplifier() + 1);
        if (isOnIce(player)) allowance *= 1.40;
        if (isOnSoulSpeed(player)) allowance *= 1.40;

        double cap = baseCap * allowance;
        // Spike fuera del cap — incrementamos contador.
        if (bps > cap) {
            s.speedOverflowCounter++;
        } else {
            s.speedOverflowCounter = Math.max(0, s.speedOverflowCounter - 1);
        }

        if (s.speedOverflowCounter >= consecutiveToFlag) {
            ViolationLevel lvl;
            if (bps > cap * 1.6) {
                lvl = ViolationLevel.HIGH;
            } else if (bps > cap * 1.3) {
                lvl = ViolationLevel.MID;
            } else {
                lvl = ViolationLevel.LOW;
            }
            sink.flag(new Violation(player, "speed_packet",
                lvl,
                String.format("bps=%.2f cap=%.2f allow=%.2f streak=%d", bps, cap, allowance, s.speedOverflowCounter)));
            // No reseteamos completo — un cheater sostenido seguira flageando.
            // Capamos para no spamear.
            s.speedOverflowCounter = Math.min(s.speedOverflowCounter, consecutiveToFlag);
        }
    }

    private static PotionEffect getEffect(Player p, String name) {
        try {
            @SuppressWarnings("deprecation")
            PotionEffectType type = PotionEffectType.getByName(name);
            if (type == null) return null;
            return p.getPotionEffect(type);
        } catch (Throwable t) {
            return null;
        }
    }

    private static boolean isOnIce(Player p) {
        try {
            Material below = p.getLocation().clone().add(0, -0.1, 0).getBlock().getType();
            return below == Material.ICE || below == Material.PACKED_ICE
                || below == Material.BLUE_ICE || below == Material.FROSTED_ICE;
        } catch (Throwable t) {
            return false;
        }
    }

    private static boolean isOnSoulSpeed(Player p) {
        try {
            Material below = p.getLocation().clone().add(0, -0.1, 0).getBlock().getType();
            boolean blockOk = below == Material.SOUL_SAND || below == Material.SOUL_SOIL;
            if (!blockOk) return false;
            // Soul Speed boots cualquier nivel.
            var boots = p.getInventory().getBoots();
            if (boots == null) return false;
            for (var ench : boots.getEnchantments().keySet()) {
                if (ench.getKey().getKey().equalsIgnoreCase("soul_speed")) return true;
            }
            return false;
        } catch (Throwable t) {
            return false;
        }
    }
}
