package com.argusprojects.argusmc.util;

import org.bukkit.ChatColor;
import org.bukkit.command.CommandSender;
import org.bukkit.configuration.file.FileConfiguration;

import java.util.HashMap;
import java.util.Map;

/**
 * Helper para mensajes con colores '&' y placeholders {key}.
 */
public final class Messages {

    private final FileConfiguration cfg;
    private final String prefix;

    public Messages(FileConfiguration cfg) {
        this.cfg = cfg;
        this.prefix = color(cfg.getString("messages.prefix", ""));
    }

    public String prefix() { return prefix; }

    public String get(String key, Map<String, String> placeholders) {
        String raw = cfg.getString("messages." + key, "");
        if (placeholders != null) {
            for (Map.Entry<String, String> e : placeholders.entrySet()) {
                raw = raw.replace("{" + e.getKey() + "}", e.getValue() == null ? "" : e.getValue());
            }
        }
        return color(raw);
    }

    public String get(String key) { return get(key, null); }

    public void send(CommandSender to, String key, Map<String, String> placeholders) {
        String text = get(key, placeholders);
        for (String line : text.split("\\n")) {
            to.sendMessage(line);
        }
    }

    public void sendPrefixed(CommandSender to, String key, Map<String, String> placeholders) {
        String text = get(key, placeholders);
        // Si el mensaje es multilinea, prefijo solo en la primera linea
        String[] lines = text.split("\\n", 2);
        if (lines.length > 0) to.sendMessage(prefix + lines[0]);
        if (lines.length > 1) {
            for (String l : lines[1].split("\\n")) {
                to.sendMessage(l);
            }
        }
    }

    public static Map<String, String> ph() { return new HashMap<>(); }

    public static Map<String, String> ph(String k1, String v1) {
        Map<String, String> m = new HashMap<>();
        m.put(k1, v1);
        return m;
    }
    public static Map<String, String> ph(String k1, String v1, String k2, String v2) {
        Map<String, String> m = ph(k1, v1);
        m.put(k2, v2);
        return m;
    }
    public static Map<String, String> ph(String k1, String v1, String k2, String v2, String k3, String v3) {
        Map<String, String> m = ph(k1, v1, k2, v2);
        m.put(k3, v3);
        return m;
    }
    public static Map<String, String> ph(String k1, String v1, String k2, String v2,
                                          String k3, String v3, String k4, String v4) {
        Map<String, String> m = ph(k1, v1, k2, v2, k3, v3);
        m.put(k4, v4);
        return m;
    }

    public static String color(String s) {
        if (s == null) return "";
        return ChatColor.translateAlternateColorCodes('&', s);
    }
}
