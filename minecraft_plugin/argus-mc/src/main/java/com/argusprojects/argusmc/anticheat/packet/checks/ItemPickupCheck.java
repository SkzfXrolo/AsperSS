package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Item;
import org.bukkit.entity.Player;

/**
 * Pack 48 round2 — ItemPickupCheck.
 *
 * <p>Vanilla solo permite pickup de items a ~1.5 bloques (incluyendo el
 * radio del player). Cheats "LongPickup" extienden esto a 5-10 bloques.
 *
 * <p>Se invoca desde {@link org.bukkit.event.entity.EntityPickupItemEvent}
 * en el bridge Bukkit.
 */
public final class ItemPickupCheck {

    private final ArgusPlugin plugin;

    public ItemPickupCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePickup(Player player, Item item, PacketDataStore.State s,
                             ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("item_pickup")) return;
        if (item == null) return;

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("item_pickup");
        double maxRange     = sec != null ? sec.getDouble("max_range", 2.5) : 2.5;
        double extremeRange = sec != null ? sec.getDouble("extreme_range", 5.0) : 5.0;

        double dist = player.getLocation().distance(item.getLocation());
        if (dist >= extremeRange) {
            sink.flag(new Violation(player, "item_pickup_packet",
                ViolationLevel.HIGH,
                String.format("pickup dist=%.2f", dist)));
        } else if (dist > maxRange) {
            sink.flag(new Violation(player, "item_pickup_packet",
                ViolationLevel.MID,
                String.format("pickup dist=%.2f", dist)));
        }
    }
}
