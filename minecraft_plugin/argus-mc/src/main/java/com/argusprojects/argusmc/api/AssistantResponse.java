package com.argusprojects.argusmc.api;

/**
 * Respuesta del endpoint conversacional del Argus AI Oracle (Pack 46).
 *
 * <p>El backend recibe texto libre del staff y devuelve una respuesta
 * humanizada basada en datos reales (historial de jugadores, decisiones
 * pasadas, modelo ML, etc.).
 *
 * <p>Endpoint asociado: {@code POST /api/plugin/assistant/query}.
 */
public final class AssistantResponse {
    /** True si el backend respondio sin errores. */
    public boolean success;

    /** Intent detectado por el classifier (status, history, advice, etc.). */
    public String intent;

    /** Respuesta narrativa generada por el assistant. */
    public String answer;

    /** True si la consulta era sobre un jugador y el assistant no encontro data. */
    public boolean missingData;

    /** Mensaje de error si success=false. */
    public String error;
}
