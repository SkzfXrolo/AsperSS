package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;
import org.bukkit.inventory.ItemStack;

/**
 * Pack 48 #488 — AutoTotemCheck (totem swap automatico tras hit fatal).
 *
 * <p>Un AutoTotem hack detecta cuando el jugador esta a punto de morir y
 * swap-ea un Totem of Undying al offhand antes de que el damage lo mate.
 * El patron caracteristico:
 * <ol>
 *   <li>El jugador recibe damage que lo dejaria en {@code health &lt; 1}.</li>
 *   <li>El cliente envia un InventoryClick (o swap-hands) en &lt;50ms.</li>
 *   <li>Despues de ese click, el offhand contiene un Totem.</li>
 * </ol>
 *
 * <p>Un humano legitimo no puede reaccionar mas rapido que ~150-200ms.
 * &lt;100ms es bot. Aplicamos thresholds escalonados.
 *
 * <p>NOTA: este check se llama DESPUES de que el inventory event ya tuvo
 * efecto (no podemos cancelarlo desde Bukkit MONITOR), pero el flag y la
 * accion del ViolationManager corren normalmente.
 */
public final class AutoTotemCheck {

    private final ArgusPlugin plugin;

    public AutoTotemCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /**
     * Llamado desde el bridge Bukkit cuando un inventory event mueve algo
     * al offhand del jugador. Verifica si fue un Totem y si el timing
     * sospecha de AutoTotem.
     *
     * @param resultingOffhand item que termino en el offhand DESPUES del click.
     */
    public void handleOffhandUpdate(Player player, PacketDataStore.State s, long now,
                                    ItemStack resultingOffhand, ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("auto_totem")) return;
        if (resultingOffhand == null) return;
        if (resultingOffhand.getType() != Material.TOTEM_OF_UNDYING) return;

        if (s.lastDamageTakenMs == 0L) return;
        long sinceHit = now - s.lastDamageTakenMs;
        if (sinceHit < 0L || sinceHit > 600L) return;
        // Solo flageamos si el damage fue casi-fatal — un swap defensivo en
        // hits normales es solo gameplay legitimo.
        // Threshold: post-damage health <= 4 (2 hearts). Bots de AutoTotem
        // usan thresholds mas extremos (1-2 hearts).
        double healthAfterDmg = s.lastDamageHealthAfter;
        if (healthAfterDmg > 4.0) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("auto_totem");
        long fastMs    = sec != null ? sec.getLong("react_ms_fast",    50L)  : 50L;
        long midMs     = sec != null ? sec.getLong("react_ms_mid",     100L) : 100L;
        long slowMs    = sec != null ? sec.getLong("react_ms_slow",    200L) : 200L;

        if (sinceHit < fastMs) {
            sink.flag(new Violation(player, "auto_totem_packet",
                ViolationLevel.HIGH,
                String.format("react=%dms healthAfter=%.1f (<%dms threshold)",
                    sinceHit, healthAfterDmg, fastMs)));
        } else if (sinceHit < midMs) {
            sink.flag(new Violation(player, "auto_totem_packet",
                ViolationLevel.MID,
                String.format("react=%dms healthAfter=%.1f", sinceHit, healthAfterDmg)));
        } else if (sinceHit < slowMs) {
            sink.flag(new Violation(player, "auto_totem_packet",
                ViolationLevel.LOW,
                String.format("react=%dms healthAfter=%.1f", sinceHit, healthAfterDmg)));
        }
    }
}
