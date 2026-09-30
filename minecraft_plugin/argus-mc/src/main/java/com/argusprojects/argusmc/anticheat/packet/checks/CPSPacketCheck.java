package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.entity.Player;

/** @deprecated Delegado al {@link com.argusprojects.argusmc.anticheat.autoclick.AutoClickEngine}. */
@Deprecated
public final class CPSPacketCheck {

    private final ArgusPlugin plugin;

    public CPSPacketCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handleSwing(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        plugin.getAutoClickEngine().onSwing(player, now, sink::flag);
    }

    public void handleAttack(Player player, PacketDataStore.State s, long now, ViolationSink sink) {
        plugin.getAutoClickEngine().onAttack(player, now, sink::flag);
    }
}
