package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;
import org.bukkit.util.BoundingBox;
import org.bukkit.util.Vector;

import java.util.Arrays;
import java.util.Collection;

/**
 * TriggerBot: pega solo en el instante en que la mira entra en el hitbox (reaccion 0-1 tick) y nunca
 * pega al aire. Un humano que hace spam tiene reaccion corta pero muchos swings al aire; uno que pega
 * con calma casi no falla pero reacciona en 3+ ticks (150ms+). Las dos cosas juntas no son humanas.
 * Ojo con el orden: el cliente ataca DURANTE el tick y manda la rotacion nueva al FINAL, asi que un
 * ataque "antes" de que la rotacion del server entre al objetivo, seguido de la que entra, es reaccion 0.
 */
public final class TriggerBotCheck {

    public static final int REACTIONS = 10;
    private static final double RANGE = 4.5;

    private final ArgusPlugin plugin;

    public TriggerBotCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /** Llamar con la rotacion/posicion ya actualizada en el state. */
    public void handleLook(Player player, PacketDataStore.State s, Collection<Entity> nearby, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("triggerbot")) return;
        boolean on = lookingAtEntity(player, s, nearby);
        if (on && !s.trigOnTarget) {
            if (s.trigPendingAttackTick >= 0 && s.clientTicks - s.trigPendingAttackTick <= 1) {
                record(player, s, 0, sink);   // ataco en el mismo tick en que la mira entro
            } else {
                s.trigEnterTick = s.clientTicks;
                s.trigArmed = true;
            }
        }
        if (!on) s.trigArmed = false;
        s.trigPendingAttackTick = -1;
        s.trigOnTarget = on;
    }

    public void handleAttack(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("triggerbot")) return;
        if (now - s.trigLastAttackMs > 3_000L) resetWindow(s);
        s.trigLastAttackMs = now;
        s.trigAttacks++;
        if (s.trigArmed) {
            s.trigArmed = false;
            record(player, s, (int) (s.clientTicks - s.trigEnterTick), sink);
        } else if (!s.trigOnTarget) {
            s.trigPendingAttackTick = s.clientTicks;
        }
    }

    public void handleSwing(PacketDataStore.State s) {
        s.trigSwings++;
    }

    private void record(Player player, PacketDataStore.State s, int reactionTicks, ViolationSink sink) {
        s.trigReactions[s.trigReactionCount % REACTIONS] = reactionTicks;
        if (++s.trigReactionCount < REACTIONS) return;
        int[] r = Arrays.copyOf(s.trigReactions, REACTIONS);
        Arrays.sort(r);
        int median = r[REACTIONS / 2];
        double missRatio = s.trigSwings <= 0 ? 0 : Math.max(0, s.trigSwings - s.trigAttacks) / (double) s.trigSwings;
        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("triggerbot");
        double maxMiss = sec != null ? sec.getDouble("max_miss_ratio", 0.10) : 0.10;
        if (isTrigger(median, missRatio, s.trigAttacks, maxMiss)) {
            s.trigFlags++;
            sink.flag(new Violation(player, "triggerbot_packet",
                s.trigFlags >= 2 ? ViolationLevel.HIGH : ViolationLevel.MID,
                String.format("reaccion mediana %d ticks al entrar la mira, %.0f%% de swings al aire (%d golpes)",
                    median, missRatio * 100, s.trigAttacks)));
        }
        resetWindow(s);
    }

    static boolean isTrigger(int medianReactionTicks, double missRatio, int attacks, double maxMiss) {
        return attacks >= REACTIONS && medianReactionTicks <= 1 && missRatio < maxMiss;
    }

    private static void resetWindow(PacketDataStore.State s) {
        s.trigReactionCount = 0;
        s.trigSwings = 0;
        s.trigAttacks = 0;
    }

    private static boolean lookingAtEntity(Player player, PacketDataStore.State s, Collection<Entity> nearby) {
        double eyeY = s.lastY + (s.packetSneaking ? 1.27 : 1.62);
        Vector eye = new Vector(s.lastX, eyeY, s.lastZ);
        double yaw = Math.toRadians(s.lastYaw), pitch = Math.toRadians(s.lastPitch);
        Vector dir = new Vector(-Math.sin(yaw) * Math.cos(pitch), -Math.sin(pitch), Math.cos(yaw) * Math.cos(pitch));
        for (Entity e : nearby) {
            if (!(e instanceof LivingEntity) || e.getEntityId() == player.getEntityId()) continue;
            BoundingBox bb;
            try {
                bb = e.getBoundingBox().clone().expand(0.1);
            } catch (Throwable t) {
                continue;
            }
            if (bb.getCenter().distanceSquared(eye) > (RANGE + 2) * (RANGE + 2)) continue;
            if (bb.rayTrace(eye, dir, RANGE) != null) return true;
        }
        return false;
    }
}
