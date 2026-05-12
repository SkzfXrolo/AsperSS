package com.argusprojects.argusmc.api;

import org.junit.jupiter.api.Test;

import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import static org.junit.jupiter.api.Assertions.*;

class JsonMiniTest {

    @Test
    void escapesQuotesAndBackslashes() {
        assertEquals("hola \\\"mundo\\\" \\\\", JsonMini.escape("hola \"mundo\" \\"));
    }

    @Test
    void escapesNewlinesTabs() {
        assertEquals("a\\nb\\tc", JsonMini.escape("a\nb\tc"));
    }

    @Test
    void escapesNullReturnsEmpty() {
        assertEquals("", JsonMini.escape(null));
    }

    @Test
    void toJsonProducesExpectedShape() {
        Map<String, String> m = new LinkedHashMap<>();
        m.put("a", "1");
        m.put("b", "2");
        String json = JsonMini.toJson(m);
        assertEquals("{\"a\":\"1\",\"b\":\"2\"}", json);
    }

    @Test
    void findStringReadsBasic() {
        String body = "{\"name\":\"argus\",\"version\":\"1.0\"}";
        assertEquals("argus", JsonMini.findString(body, "name"));
        assertEquals("1.0", JsonMini.findString(body, "version"));
    }

    @Test
    void findStringReturnsNullForAbsent() {
        String body = "{\"name\":\"argus\"}";
        assertNull(JsonMini.findString(body, "missing"));
    }

    @Test
    void findBoolReadsTrueFalse() {
        String body = "{\"success\":true,\"authenticated\":false}";
        assertEquals(Boolean.TRUE, JsonMini.findBool(body, "success"));
        assertEquals(Boolean.FALSE, JsonMini.findBool(body, "authenticated"));
    }

    @Test
    void findDoubleParsesFloats() {
        String body = "{\"score\":0.85,\"rate\":-12.5}";
        assertEquals(0.85, JsonMini.findDouble(body, "score", -1), 1e-9);
        assertEquals(-12.5, JsonMini.findDouble(body, "rate", -1), 1e-9);
    }

    @Test
    void findDoubleReturnsDefaultForAbsent() {
        String body = "{\"x\":1}";
        assertEquals(42.0, JsonMini.findDouble(body, "missing", 42.0), 1e-9);
    }

    @Test
    void extractMessagesFromSuggestionsReadsArray() {
        String body = "{\"suggestions\":[{\"player_name\":\"a\",\"message\":\"hola\"},"
            + "{\"player_name\":\"b\",\"message\":\"chau\"}]}";
        List<String> out = JsonMini.extractMessagesFromSuggestions(body);
        assertEquals(2, out.size());
        assertEquals("hola", out.get(0));
        assertEquals("chau", out.get(1));
    }

    @Test
    void extractMessagesFromSuggestionsEmptyWhenNoArray() {
        assertTrue(JsonMini.extractMessagesFromSuggestions("{\"x\":1}").isEmpty());
        assertTrue(JsonMini.extractMessagesFromSuggestions(null).isEmpty());
    }
}
