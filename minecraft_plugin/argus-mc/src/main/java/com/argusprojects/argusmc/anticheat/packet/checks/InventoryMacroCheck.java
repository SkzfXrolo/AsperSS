package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * ChestStealer / InvCleaner / AutoArmor de inventario: clicks de inventario hechos por un macro.
 * - Ritmo de maquina: 8 clicks seguidos a intervalo casi identico (desvio < 12ms) y rapido.
 * - Rafaga: 4+ clicks en 50ms (una mano no hace 4 clicks en un tick).
 * - Click instantaneo al abrir un cofre: antes del ping + 50ms (no hubo tiempo de ver ni mover el mouse).
 */
public final class InventoryMacroCheck {

    public static final int RING = 16;

    private final ArgusPlugin plugin;

    public InventoryMacroCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleClick(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("inventory_macro")) return;
        if (s.invClickCount > 0 && now - s.invClickTimes[(s.invClickCount - 1) % RING] > 1_000L) s.invClickCount = 0;
        s.invClickTimes[s.invClickCount % RING] = now;
        s.invClickCount++;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("inventory_macro");
        int n = sec != null ? sec.getInt("rhythm_clicks", 8) : 8;
        long[] times = last(s, Math.min(s.invClickCount, RING));

        String why = null;
        if (times.length > n && isRoboticRhythm(times, n)) {
            why = String.format("%d clicks de inventario a ritmo fijo (macro)", n);
        } else if (isBurst(times, 4, 50L)) {
            why = "4+ clicks de inventario en un tick";
        }
        if (s.invFirstClickPending) {
            s.invFirstClickPending = false;
            long dt = now - s.inventoryOpenSinceMs;
            if (dt >= 0 && dt < Math.min(s.pingMs, 300L) + 50L) {
                if (now - s.invFastOpenWindowMs > 60_000L) {
                    s.invFastOpenWindowMs = now;
                    s.invFastOpenHits = 0;
                }
                if (++s.invFastOpenHits >= 3 && why == null) {
                    why = String.format("click %dms despues de abrir el cofre x%d (sin tiempo de reaccion)", dt, s.invFastOpenHits);
                }
            }
        }
        if (why == null || now - s.lastInvMacroFlagMs < 2_000L) return;
        s.lastInvMacroFlagMs = now;
        if (now - s.invMacroWindowMs > 30_000L) {
            s.invMacroWindowMs = now;
            s.invMacroHits = 0;
        }
        s.invMacroHits++;
        sink.flag(new Violation(player, "inventory_macro_packet",
            s.invMacroHits >= 3 ? ViolationLevel.HIGH : ViolationLevel.MID, why));
    }

    private static long[] last(PacketDataStore.State s, int k) {
        long[] t = new long[k];
        for (int i = 0; i < k; i++) t[i] = s.invClickTimes[(s.invClickCount - k + i) % RING];
        return t;
    }

    /** Ultimos n intervalos: media < 150ms y desvio < 12ms. */
    static boolean isRoboticRhythm(long[] times, int n) {
        if (times.length < n + 1) return false;
        double sum = 0, sum2 = 0;
        for (int i = times.length - n; i < times.length; i++) {
            double dt = times[i] - times[i - 1];
            sum += dt;
            sum2 += dt * dt;
        }
        double mean = sum / n;
        double std = Math.sqrt(Math.max(0, sum2 / n - mean * mean));
        return mean < 150 && std < 12;
    }

    /** k clicks (los ultimos) dentro de windowMs. */
    static boolean isBurst(long[] times, int k, long windowMs) {
        return times.length >= k && times[times.length - 1] - times[times.length - k] <= windowMs;
    }
}
