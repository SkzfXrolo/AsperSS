package com.argusprojects.argusmc.anticheat;

public enum ViolationLevel {
    LOW(1),
    MID(2),
    HIGH(3),
    CRITICAL(4);

    private final int weight;

    ViolationLevel(int weight) {
        this.weight = weight;
    }

    public int weight() { return weight; }

    public boolean atLeast(ViolationLevel other) {
        return this.weight >= other.weight;
    }
}
