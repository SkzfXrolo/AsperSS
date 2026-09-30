package com.argusprojects.argusmc.anticheat;

import java.util.Locale;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public final class ViolationFormatter {

    private static final Pattern SCORE_PATTERN = Pattern.compile(
        "score=([\\d.]+).*cps=(\\d+).*burst=(\\d+).*cv=([\\d.]+).*stddev=([\\d.]+)ms");
    private static final Pattern CPS_MAX_PATTERN = Pattern.compile("cps=(\\d+).*max=(\\d+)");
    private static final Pattern CPS_PATTERN = Pattern.compile("cps=(\\d+)");
    private static final Pattern BPS_PATTERN = Pattern.compile("bps=([\\d.]+).*cap=([\\d.]+)");
    private static final Pattern STDEV_PATTERN = Pattern.compile("CPS=([\\d.]+).*stddev=([\\d.]+)ms");
    private static final Pattern TIMER_PATTERN = Pattern.compile("packets=(\\d+).*ratio=([\\d.]+)x");

    private ViolationFormatter() {}

    public static String checkLabel(String checkName) {
        if (checkName == null) return "Desconocido";
        return switch (checkName) {
            case "cps_packet" -> "Clicks por segundo";
            case "autoclicker", "autoclicker_packet" -> "AutoClicker";
            case "autoclicker_advanced_packet" -> "AutoClicker robotico";
            case "autoclicker_variance" -> "AutoClicker (ritmo fijo)";
            case "speed_packet", "speed" -> "Velocidad";
            case "timer_packet", "timer" -> "Timer";
            case "timer_jitter_packet" -> "Timer irregular";
            case "ping_spoof_packet" -> "Ping sospechoso";
            case "reach", "reach_packet", "reach_3d_packet" -> "Reach";
            case "killaura_no_swing", "killaura_no_swing_packet" -> "KillAura (sin swing)";
            case "killaura_fov_packet" -> "KillAura (angulo)";
            case "fly" -> "Fly";
            case "jesus" -> "Jesus";
            case "nofall" -> "NoFall";
            case "scaffold" -> "Scaffold";
            case "hit_through_wall" -> "Hit through wall";
            case "admin_testpacket" -> "Prueba admin";
            default -> {
                String n = checkName.replace('_', ' ');
                if (n.endsWith(" packet")) n = n.substring(0, n.length() - 7);
                yield capitalize(n);
            }
        };
    }

    public static String formatSummary(String checkName, String details) {
        if (details == null || details.isBlank()) return "comportamiento sospechoso";
        String d = details.trim();

        Matcher m = SCORE_PATTERN.matcher(d);
        if (m.find()) {
            return String.format(Locale.ROOT,
                "%s CPS, burst %s, ritmo sospechoso (cv=%s, stddev=%sms)",
                m.group(2), m.group(3), m.group(4), m.group(5));
        }
        m = CPS_MAX_PATTERN.matcher(d);
        if (m.find()) {
            return String.format(Locale.ROOT, "%s clics/seg (limite %s)", m.group(1), m.group(2));
        }
        m = CPS_PATTERN.matcher(d);
        if (m.find() && (checkName.contains("cps") || checkName.contains("autoclicker"))) {
            return String.format(Locale.ROOT, "%s clics por segundo", m.group(1));
        }
        m = STDEV_PATTERN.matcher(d);
        if (m.find()) {
            return String.format(Locale.ROOT, "%s CPS con ritmo demasiado perfecto (%.1fms)", m.group(1), Double.parseDouble(m.group(2)));
        }
        m = BPS_PATTERN.matcher(d);
        if (m.find()) {
            return String.format(Locale.ROOT, "se movio a %.1f bloques/seg (limite %.1f)", Double.parseDouble(m.group(1)), Double.parseDouble(m.group(2)));
        }
        m = TIMER_PATTERN.matcher(d);
        if (m.find()) {
            return String.format(Locale.ROOT, "envio demasiados movimientos (x%s)", m.group(2));
        }
        if (d.contains("rtt=0ms") || d.contains("rtt=1ms")) {
            return "ping local/imposible en red real";
        }
        if (d.startsWith("dist=")) {
            return d.replace("dist=", "distancia ").replace("max=", "max ").replace("b", " bloques");
        }
        if (d.startsWith("swing fue hace")) {
            return "golpeo sin animacion de brazo (" + d + ")";
        }
        if (d.contains("(aire)")) {
            return d.replace("(aire)", " — clics al aire");
        }
        return d.length() > 72 ? d.substring(0, 69) + "..." : d;
    }

    public static String staffLine(Violation v) {
        String levelTag = switch (v.level) {
            case LOW -> "&e";
            case MID -> "&c";
            case HIGH -> "&4&l";
            case CRITICAL -> "&4&l";
        };
        return String.format("&8[&6AC&8] %s%s &7| &f%s &7| &f%s&7: %s",
            levelTag,
            v.level.name(),
            v.playerName,
            checkLabel(v.checkName),
            formatSummary(v.checkName, v.details));
    }

    private static String capitalize(String s) {
        if (s.isEmpty()) return s;
        return Character.toUpperCase(s.charAt(0)) + s.substring(1);
    }
}
