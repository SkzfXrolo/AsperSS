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

    /**
     * Construye un mapa key->value a partir de una lista plana de pares.
     *
     * <p>Acepta cualquier numero PAR de argumentos (kv-varargs):
     * <pre>ph("a", "1", "b", "2", "c", "3")</pre>
     * Si se pasa un numero impar, el ultimo se ignora silenciosamente.
     *
     * <p>Reemplaza los antiguos overloads fijos (2/4/6/8 args) que limitaban
     * los placeholders a 4 maximo y rompian /argus info (que necesita 6).
     */
    public static Map<String, String> ph(String... kv) {
        Map<String, String> m = new HashMap<>();
        if (kv == null) return m;
        int n = kv.length - (kv.length % 2);
        for (int i = 0; i < n; i += 2) {
            m.put(kv[i], kv[i + 1]);
        }
        return m;
    }

    public static String color(String s) {
        if (s == null) return "";
        return ChatColor.translateAlternateColorCodes('&', s);
    }
}
