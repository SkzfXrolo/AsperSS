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

    /** Copia con un nivel distinto (Pack 48 #525: per-check level override). */
    private Violation(UUID uuid, String name, String checkName, ViolationLevel level, String details, long ts) {
        this.playerUuid  = uuid;
        this.playerName  = name;
        this.checkName   = checkName;
        this.level       = level;
        this.details     = details == null ? "" : details;
        this.timestampMs = ts;
    }

    public Violation withLevel(ViolationLevel newLevel) {
        if (newLevel == this.level) return this;
        return new Violation(playerUuid, playerName, checkName, newLevel, details, timestampMs);
    }

    @Override
    public String toString() {
        return "Violation{" + level + " " + checkName + " by " + playerName + " (" + details + ")}";
    }
}
