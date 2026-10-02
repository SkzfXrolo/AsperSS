package com.argusprojects.argusmc.anticheat;

import org.bukkit.entity.Player;

import java.util.UUID;

public final class Violation {

    public final UUID            playerUuid;
    public final String          playerName;
    public final String          checkName;
    public final ViolationLevel  level;
    public final String          details;
    public final long            timestampMs;

    public Violation(Player player, String checkName, ViolationLevel level, String details) {
        this.playerUuid  = player.getUniqueId();
        this.playerName  = player.getName();
        this.checkName   = checkName;
        this.level       = level;
        this.details     = details == null ? "" : details;
        this.timestampMs = System.currentTimeMillis();
    }

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
