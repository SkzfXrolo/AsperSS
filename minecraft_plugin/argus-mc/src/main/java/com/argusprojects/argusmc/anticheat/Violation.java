package com.argusprojects.argusmc.anticheat;

import org.bukkit.entity.Player;

import java.util.UUID;

/**
 * Una deteccion concreta producida por un Check del anti-cheat.
 *
 * <p>Es un record-like inmutable: lo crea el check, lo registra el
 * {@link ViolationManager}, y se serializa para enviarlo al backend
 * y/o al webhook de Discord.
 */
public final class Violation {

    public final UUID            playerUuid;
    public final String          playerName;
    public final String          checkName;     // "reach", "killaura_angle", ...
    public final ViolationLevel  level;
    public final String          details;       // texto humano legible
    public final long            timestampMs;

    public Violation(Player player, String checkName, ViolationLevel level, String details) {
        this.playerUuid  = player.getUniqueId();
        this.playerName  = player.getName();
        this.checkName   = checkName;
        this.level       = level;
        this.details     = details == null ? "" : details;
        this.timestampMs = System.currentTimeMillis();
    }

    @Override
    public String toString() {
        return "Violation{" + level + " " + checkName + " by " + playerName + " (" + details + ")}";
    }
}
