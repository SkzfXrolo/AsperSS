package com.argusprojects.argusmc.anticheat;

/**
 * Veredicto del Argus AI Oracle (Pack 44).
 *
 * <p>El backend Argus (asperss.onrender.com) corre el motor heuristico
 * humanizado y devuelve esta estructura para que el plugin decida si
 * sobreescribe la accion local del {@link ViolationManager}.
 *
 * <p>Reglas de merge:
 * <ul>
 *   <li>Si {@code mergedAction} viene set por el backend, se respeta.</li>
 *   <li>Si no, el plugin compara su propio rank de severidad con
 *       {@link #action} y se queda con el MAS SEVERO.</li>
 * </ul>
 */
public final class AiVerdict {
    public String action;        // none | watch | ss | kick | ban
    public String mergedAction;  // accion final teniendo en cuenta la del plugin
    public String reasoning;     // texto humanizado para chat staff
    public String topFactor;     // ej: "killaura_no_swing HIGH"
    public double score;         // 0.0 - 1.0
    public double confidence;    // 0.0 - 1.0
}
