package com.argusprojects.argusmc.api;

import java.util.Map;

/**
 * Mini parser/serializer JSON deliberadamente acotado:
 *  - serializa Map&lt;String,String&gt; (escapes basicos)
 *  - extrae STRING / INT / LONG / BOOL de respuestas planas no anidadas.
 *
 * <p>Suficiente para los 3-4 endpoints que usa este plugin. Si el backend
 * empieza a devolver objetos anidados, conviene agregar Gson como dependencia.
 */
final class JsonMini {

    private JsonMini() {}

    static String toJson(Map<String, String> data) {
        StringBuilder sb = new StringBuilder("{");
        boolean first = true;
        for (Map.Entry<String, String> e : data.entrySet()) {
            if (!first) sb.append(',');
            first = false;
            sb.append('"').append(escape(e.getKey())).append("\":\"")
              .append(escape(e.getValue())).append('"');
        }
        sb.append('}');
        return sb.toString();
    }

    static String findString(String body, String key) {
        if (body == null || key == null) return null;
        // Busca la key (con comillas) y devuelve el valor string entre comillas.
        String needle = '"' + key + '"';
        int i = body.indexOf(needle);
        if (i < 0) return null;
        i = body.indexOf(':', i + needle.length());
        if (i < 0) return null;
        i++;
        // Skip whitespace
        while (i < body.length() && Character.isWhitespace(body.charAt(i))) i++;
        if (i >= body.length()) return null;
        if (body.charAt(i) == 'n') return null; // null
        if (body.charAt(i) != '"') return null; // no es string
        i++; // open quote
        StringBuilder sb = new StringBuilder();
        boolean esc = false;
        for (; i < body.length(); i++) {
            char c = body.charAt(i);
            if (esc) {
                switch (c) {
                    case 'n': sb.append('\n'); break;
                    case 't': sb.append('\t'); break;
                    case 'r': sb.append('\r'); break;
                    case '"': sb.append('"'); break;
                    case '\\': sb.append('\\'); break;
                    case '/': sb.append('/'); break;
                    default: sb.append(c); break;
                }
                esc = false;
            } else if (c == '\\') {
                esc = true;
            } else if (c == '"') {
                return sb.toString();
            } else {
                sb.append(c);
            }
        }
        return null;
    }

    static Integer findInt(String body, String key) {
        Long v = findLongRaw(body, key);
        return v == null ? null : v.intValue();
    }

    static long findLong(String body, String key, long defaultValue) {
        Long v = findLongRaw(body, key);
        return v == null ? defaultValue : v;
    }

    static Boolean findBool(String body, String key) {
        if (body == null || key == null) return null;
        String needle = '"' + key + '"';
        int i = body.indexOf(needle);
        if (i < 0) return null;
        i = body.indexOf(':', i + needle.length());
        if (i < 0) return null;
        i++;
        while (i < body.length() && Character.isWhitespace(body.charAt(i))) i++;
        if (body.regionMatches(i, "true", 0, 4))  return Boolean.TRUE;
        if (body.regionMatches(i, "false", 0, 5)) return Boolean.FALSE;
        return null;
    }

    private static Long findLongRaw(String body, String key) {
        if (body == null || key == null) return null;
        String needle = '"' + key + '"';
        int i = body.indexOf(needle);
        if (i < 0) return null;
        i = body.indexOf(':', i + needle.length());
        if (i < 0) return null;
        i++;
        while (i < body.length() && Character.isWhitespace(body.charAt(i))) i++;
        StringBuilder sb = new StringBuilder();
        if (i < body.length() && body.charAt(i) == '-') {
            sb.append('-');
            i++;
        }
        while (i < body.length() && Character.isDigit(body.charAt(i))) {
            sb.append(body.charAt(i));
            i++;
        }
        if (sb.length() == 0 || (sb.length() == 1 && sb.charAt(0) == '-')) return null;
        try {
            return Long.parseLong(sb.toString());
        } catch (NumberFormatException ex) {
            return null;
        }
    }

    private static String escape(String raw) {
        if (raw == null) return "";
        StringBuilder sb = new StringBuilder(raw.length() + 8);
        for (int i = 0; i < raw.length(); i++) {
            char c = raw.charAt(i);
            switch (c) {
                case '"':  sb.append("\\\""); break;
                case '\\': sb.append("\\\\"); break;
                case '\n': sb.append("\\n"); break;
                case '\r': sb.append("\\r"); break;
                case '\t': sb.append("\\t"); break;
                default:
                    if (c < 0x20) {
                        sb.append(String.format("\\u%04x", (int) c));
                    } else {
                        sb.append(c);
                    }
            }
        }
        return sb.toString();
    }
}
