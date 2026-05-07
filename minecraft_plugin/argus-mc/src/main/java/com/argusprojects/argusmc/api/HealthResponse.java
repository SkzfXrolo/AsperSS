package com.argusprojects.argusmc.api;

/**
 * Respuesta del endpoint /api/plugin/health.
 */
public final class HealthResponse {
    public final boolean success;
    public final boolean authenticated;
    public final String  status;
    public final Integer companyId;
    public final String  label;
    public final Integer dailyQuota;
    public final Integer usedToday;
    public final String  argusVersion;
    public final String  errorMessage;

    private HealthResponse(boolean success, boolean authenticated, String status, Integer companyId,
                           String label, Integer dailyQuota, Integer usedToday, String argusVersion,
                           String errorMessage) {
        this.success = success;
        this.authenticated = authenticated;
        this.status = status;
        this.companyId = companyId;
        this.label = label;
        this.dailyQuota = dailyQuota;
        this.usedToday = usedToday;
        this.argusVersion = argusVersion;
        this.errorMessage = errorMessage;
    }

    public static HealthResponse parse(int httpStatus, String body) {
        if (body == null) body = "";
        boolean ok = httpStatus >= 200 && httpStatus < 300;
        if (!ok) {
            String err = JsonMini.findString(body, "error");
            if (err == null || err.isEmpty()) err = "HTTP " + httpStatus;
            return new HealthResponse(false, false, "error", null, null, null, null, null, err);
        }
        Boolean auth = JsonMini.findBool(body, "authenticated");
        return new HealthResponse(
            true,
            auth != null && auth,
            JsonMini.findString(body, "status"),
            JsonMini.findInt(body, "company_id"),
            JsonMini.findString(body, "label"),
            JsonMini.findInt(body, "daily_quota"),
            JsonMini.findInt(body, "used_today"),
            JsonMini.findString(body, "argus_version"),
            null
        );
    }

    public static HealthResponse error(String msg) {
        return new HealthResponse(false, false, "error", null, null, null, null, null, msg);
    }
}
