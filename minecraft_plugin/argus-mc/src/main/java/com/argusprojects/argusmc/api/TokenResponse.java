package com.argusprojects.argusmc.api;

/**
 * Respuesta del endpoint /api/plugin/issue-token.
 */
public final class TokenResponse {
    public final boolean success;
    public final int httpStatus;

    public final String shortCode;
    public final String downloadUrl;
    public final String downloadPageUrl;
    public final long expiresInSeconds;
    public final Integer companyId;
    public final Integer remainingQuotaToday;

    public final String errorMessage;

    private TokenResponse(boolean success, int httpStatus, String shortCode, String downloadUrl,
                          String downloadPageUrl, long expiresInSeconds, Integer companyId,
                          Integer remainingQuotaToday, String errorMessage) {
        this.success = success;
        this.httpStatus = httpStatus;
        this.shortCode = shortCode;
        this.downloadUrl = downloadUrl;
        this.downloadPageUrl = downloadPageUrl;
        this.expiresInSeconds = expiresInSeconds;
        this.companyId = companyId;
        this.remainingQuotaToday = remainingQuotaToday;
        this.errorMessage = errorMessage;
    }

    public static TokenResponse parse(int httpStatus, String body) {
        if (body == null) body = "";
        if (httpStatus >= 200 && httpStatus < 300) {
            String code = JsonMini.findString(body, "short_code");
            if (code == null || code.isEmpty()) {
                return error("Respuesta sin short_code (status " + httpStatus + ")");
            }
            return new TokenResponse(
                true,
                httpStatus,
                code,
                JsonMini.findString(body, "download_url"),
                JsonMini.findString(body, "download_page_url"),
                JsonMini.findLong(body, "expires_in_seconds", 30 * 60),
                JsonMini.findInt(body, "company_id"),
                JsonMini.findInt(body, "remaining_quota_today"),
                null
            );
        }
        String err = JsonMini.findString(body, "error");
        if (err == null || err.isEmpty()) err = "HTTP " + httpStatus;
        return new TokenResponse(false, httpStatus, null, null, null, 0, null, null, err);
    }

    public static TokenResponse error(String msg) {
        return new TokenResponse(false, 0, null, null, null, 0, null, null, msg);
    }
}
