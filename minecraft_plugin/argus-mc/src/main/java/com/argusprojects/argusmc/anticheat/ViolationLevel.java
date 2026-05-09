package com.argusprojects.argusmc.anticheat;

/**
 * Severidad de una violation generada por un check del anti-cheat.
 *
 * <p>Cada nivel tiene una accion default que el {@link ViolationManager}
 * aplica al acumularse suficientes en la sliding window:
 *
 * <ul>
 *   <li><b>LOW</b>: Solo alerta in-game al staff con permiso
 *       <code>argus.alerts</code>. Util para checks ruidosos que
 *       sirven para auditoria (ej: clicks borderline, microspeed).</li>
 *   <li><b>MID</b>: Kick automatico con razon legible. El jugador
 *       puede reconectarse y se le borra el acumulado. Apto para
 *       checks confiables pero falseables por lag (ej: Reach 4.6b).</li>
 *   <li><b>HIGH</b>: Kick + auto-emision de SS forzado al reconectar.
 *       Cuando vuelva, el plugin guarda el nick del jugador en una
 *       lista y, al detectarlo en chat/cmd, le pide pasar SS o lo
 *       expulsa de nuevo. Para checks irrefutables (Reach &gt; 6b
 *       sostenido, killaura con angulo imposible).</li>
 *   <li><b>CRITICAL</b>: Ban temporal (configurable). Para cheats
 *       que NO se pueden falsear ni con lag extremo (ej: enviar
 *       packets imposibles, fly por &gt; 100 ticks sin fall).</li>
 * </ul>
 */
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
