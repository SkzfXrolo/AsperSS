package com.argusprojects.argusmc.oracle;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;

/**
 * Pack 48 round 3 — Aplica el peso del Oracle a un Violation antes de
 * que llegue al ViolationManager.
 *
 * <p>Filosofía:
 * <ul>
 *   <li>weight ≈ 1.0 → no cambia nada</li>
 *   <li>weight &gt; 1.2 → sube un escalón de nivel (MID→HIGH, etc.)</li>
 *   <li>weight &lt; 0.7 → baja un escalón (HIGH→MID, MID→LOW)</li>
 *   <li>weight &lt; 0.4 → suprime el violation (devuelve null)</li>
 * </ul>
 * Estos umbrales vienen de {@code config.yml::oracle.applier}.
 *
 * <p>USO típico desde ViolationManager:
 * <pre>
 * client.evaluate(...).thenAccept(d -> {
 *   Violation adjusted = applier.apply(v, d);
 *   if (adjusted != null) flag(adjusted);
 * });
 * </pre>
 */
public final class OracleDecisionApplier {

    private final ArgusPlugin plugin;

    public OracleDecisionApplier(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public Violation apply(Violation v, OracleCache.Decision decision) {
        if (v == null) return null;
        if (decision == null || decision.weight == 1.0) return v;

        var sec = plugin.getConfig().getConfigurationSection("oracle.applier");
        double upStep   = sec != null ? sec.getDouble("upgrade_above", 1.2) : 1.2;
        double downStep = sec != null ? sec.getDouble("downgrade_below", 0.7) : 0.7;
        double suppress = sec != null ? sec.getDouble("suppress_below", 0.4) : 0.4;

        if (decision.weight <= suppress) {
            return null;
        }
        if (decision.weight >= upStep) {
            return v.withLevel(escalate(v.level));
        }
        if (decision.weight <= downStep) {
            return v.withLevel(deescalate(v.level));
        }
        return v;
    }

    private static ViolationLevel escalate(ViolationLevel l) {
        switch (l) {
            case LOW:      return ViolationLevel.MID;
            case MID:      return ViolationLevel.HIGH;
            case HIGH:     return ViolationLevel.CRITICAL;
            case CRITICAL: return ViolationLevel.CRITICAL;
        }
        return l;
    }

    private static ViolationLevel deescalate(ViolationLevel l) {
        switch (l) {
            case CRITICAL: return ViolationLevel.HIGH;
            case HIGH:     return ViolationLevel.MID;
            case MID:      return ViolationLevel.LOW;
            case LOW:      return ViolationLevel.LOW;
        }
        return l;
    }
}
