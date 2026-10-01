package com.argusprojects.argusmc.anticheat;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

/**
 * Texto de las alertas al staff. La linea del chat es corta (quien, que hack, cuantas veces,
 * gravedad); el detalle tecnico va en el hover.
 */
public final class ViolationFormatter {

    private static final Pattern SCORE_PATTERN = Pattern.compile(
        "score=([\\d.]+).*cps=(\\d+).*burst=(\\d+).*cv=([\\d.]+).*stddev=([\\d.]+)ms");
    private static final Pattern BPS_PATTERN = Pattern.compile("bps=([\\d.,]+)");
    private static final Pattern DIST_PATTERN = Pattern.compile("dist(?:_bb)?=([\\d.,]+)");
    private static final Pattern REACH3D_PATTERN = Pattern.compile("reach=([\\d.,]+)");

    private ViolationFormatter() {}

    /** Nombre del hack que el staff conoce (varios checks internos detectan el mismo hack). */
    public static String checkLabel(String checkName) {
        if (checkName == null) return "Desconocido";
        String c = checkName.endsWith("_packet") ? checkName.substring(0, checkName.length() - 7) : checkName;
        return switch (c) {
            case "reach", "reach3d", "reach_3d", "hitbox_expansion" -> "Reach";
            case "block_reach" -> "Reach (bloques)";
            case "killaura_no_swing", "killaura_noswing", "killaura_swing", "killaura_fov", "killaura_angle",
                 "killaura_aim", "killaura_rotation", "killaura_blocking", "backstab", "aimbot" -> "KillAura";
            case "hit_through_wall", "killaura_thruwall" -> "KillAura (pared)";
            case "aim_snap" -> "Aim";
            case "cps", "autoclicker", "autoclicker_variance", "autoclicker_advanced", "autoclicker_ticks" -> "AutoClicker";
            case "criticals" -> "Criticals";
            case "antikb", "velocity", "multi_velocity" -> "AntiKB";
            case "speed" -> "Speed";
            case "strafe" -> "Strafe";
            case "fly", "jetpack", "melee_fly", "boat_fly", "boat_fly_advanced" -> "Fly";
            case "vclip" -> "VClip";
            case "step" -> "Step";
            case "spider" -> "Spider";
            case "nofall" -> "NoFall";
            case "jesus", "liquidjesus", "liquid_walk" -> "Jesus";
            case "phase", "phase_clip" -> "Phase";
            case "timer", "timer_jitter" -> "Timer";
            case "noslowdown", "noslowsneak" -> "NoSlow";
            case "safewalk" -> "SafeWalk";
            case "scaffold", "scaffold_snap", "scaffold_aim", "scaffold_rotation", "scaffold_tower" -> "Scaffold";
            case "fast_place", "fastplace" -> "FastPlace";
            case "airplace" -> "AirPlace";
            case "fast_break", "fastbreak" -> "FastBreak";
            case "nuker", "nuker_fov" -> "Nuker";
            case "block_glitch" -> "GhostHand";
            case "fasteat", "fast_eat" -> "FastEat";
            case "fastbow", "bow_aim" -> "FastBow";
            case "invalid_rotation" -> "Derp";
            case "antiafk" -> "AntiAFK";
            case "inv_move" -> "InvMove";
            case "tracers" -> "Tracers";
            case "chat_macro", "chat_spam" -> "Spam";
            case "ping_spoof" -> "PingSpoof";
            case "regen" -> "Regen";
            case "admin_test" -> "Prueba";
            default -> {
                String n = c.replace('_', ' ');
                yield n.isEmpty() ? n : Character.toUpperCase(n.charAt(0)) + n.substring(1);
            }
        };
    }

    /** Resumen legible y corto del detalle tecnico (va en el hover y en consola). */
    public static String formatSummary(String checkName, String details) {
        if (details == null || details.isBlank()) return "comportamiento sospechoso";
        String d = details.trim();
        Matcher m = SCORE_PATTERN.matcher(d);
        if (m.find()) return m.group(2) + " CPS, ritmo " + (Double.parseDouble(m.group(4)) < 0.15 ? "robotico" : "sospechoso");
        String label = checkLabel(checkName);
        if (label.equals("Reach")) {
            m = DIST_PATTERN.matcher(d);
            if (!m.find()) m = REACH3D_PATTERN.matcher(d);
            if (m.find(0)) return "pego a " + m.group(1).replace(',', '.') + " bloques";
        }
        if (label.equals("Speed")) {
            m = BPS_PATTERN.matcher(d);
            if (m.find()) return m.group(1).replace(',', '.') + " bloques/seg";
            if (d.startsWith("promedio")) return d;
        }
        if (d.startsWith("swing fue hace")) return "golpeo sin mover el brazo";
        return d.length() > 60 ? d.substring(0, 57) + "..." : d;
    }

    public static String levelColor(ViolationLevel l) {
        return switch (l) {
            case LOW -> "&e";
            case MID -> "&6";
            case HIGH -> "&c";
            case CRITICAL -> "&4";
        };
    }

    public static String levelName(ViolationLevel l) {
        return switch (l) {
            case LOW -> "Baja";
            case MID -> "Media";
            case HIGH -> "Alta";
            case CRITICAL -> "Critica";
        };
    }

    /** Barra de gravedad: 1 a 4 puntos encendidos. */
    public static String levelBar(ViolationLevel l) {
        int on = l.ordinal() + 1;
        return levelColor(l) + "●".repeat(on) + "&8" + "●".repeat(4 - on);
    }

    /** Linea del chat: "▎ARGUS » Jugador  Hack  x3  ●●●○" */
    public static String chatLine(Violation v, int count) {
        return String.format("&8▎&b&lARGUS &8» &f%s  %s%s  &8x&7%d  %s",
            v.playerName, levelColor(v.level), checkLabel(v.checkName), count, levelBar(v.level));
    }

    public static String hoverText(Violation v, int count, int pingMs) {
        return String.format("&b&l%s &7(%s)%n&7Gravedad: %s%s%n&7Veces: &f%d%n&7Detalle: &f%s%n&7Ping: &f%dms%n%n&eClick para ir hacia &f%s",
            checkLabel(v.checkName), v.checkName, levelColor(v.level), levelName(v.level), count,
            formatSummary(v.checkName, v.details), pingMs, v.playerName);
    }

    public static String consoleLine(Violation v, int count) {
        return String.format(Locale.ROOT, "&b[Argus] &f%s &8» %s%s &8x%d &7(%s) &8%s",
            v.playerName, levelColor(v.level), checkLabel(v.checkName), count, levelName(v.level),
            formatSummary(v.checkName, v.details));
    }

    /** Compat: linea plana (logs viejos / tests). */
    public static String staffLine(Violation v) {
        return chatLine(v, 1);
    }
}
