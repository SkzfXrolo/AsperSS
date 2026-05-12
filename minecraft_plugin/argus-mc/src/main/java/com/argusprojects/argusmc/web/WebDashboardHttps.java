package com.argusprojects.argusmc.web;

import com.argusprojects.argusmc.ArgusPlugin;
import com.sun.net.httpserver.HttpsConfigurator;
import com.sun.net.httpserver.HttpsParameters;
import com.sun.net.httpserver.HttpsServer;

import javax.net.ssl.KeyManagerFactory;
import javax.net.ssl.SSLContext;
import javax.net.ssl.SSLEngine;
import javax.net.ssl.SSLParameters;
import java.io.FileInputStream;
import java.net.InetSocketAddress;
import java.security.KeyStore;

/**
 * Pack 48 round 3 — soporte HTTPS opcional para el dashboard.
 *
 * <p>Si {@code web.https.enabled} es true, se levanta un
 * {@link HttpsServer} en lugar del HttpServer plano. Requiere un
 * keystore JKS o PKCS12 con la cert/clave (autosignada para uso
 * interno o real con Let's Encrypt exportada).
 *
 * <p>Generar keystore autosignado:
 * <pre>
 *   keytool -genkeypair -alias argus -keyalg RSA -keysize 2048 \
 *       -keystore argus-keystore.p12 -storetype PKCS12 \
 *       -validity 365 -storepass changeit
 * </pre>
 *
 * <p>Configurar en {@code config.yml}:
 * <pre>
 * web:
 *   enabled: true
 *   https:
 *     enabled: true
 *     keystore_path: "plugins/ArgusMC/argus-keystore.p12"
 *     keystore_password: "changeit"
 *     keystore_type: "PKCS12"
 * </pre>
 */
public final class WebDashboardHttps {

    public static HttpsServer createIfEnabled(ArgusPlugin plugin, InetSocketAddress addr)
            throws Exception {
        var sec = plugin.getConfig().getConfigurationSection("web.https");
        if (sec == null || !sec.getBoolean("enabled", false)) return null;

        String path  = sec.getString("keystore_path", "");
        String pass  = sec.getString("keystore_password", "");
        String type  = sec.getString("keystore_type", "PKCS12");
        if (path == null || path.isEmpty()) {
            plugin.getLogger().warning("[Argus/Web] https.enabled=true pero keystore_path vacio.");
            return null;
        }

        KeyStore ks = KeyStore.getInstance(type);
        try (var in = new FileInputStream(path)) {
            ks.load(in, pass.toCharArray());
        }
        KeyManagerFactory kmf = KeyManagerFactory.getInstance(
            KeyManagerFactory.getDefaultAlgorithm());
        kmf.init(ks, pass.toCharArray());

        SSLContext ctx = SSLContext.getInstance("TLSv1.3");
        ctx.init(kmf.getKeyManagers(), null, null);

        HttpsServer https = HttpsServer.create(addr, 0);
        https.setHttpsConfigurator(new HttpsConfigurator(ctx) {
            @Override
            public void configure(HttpsParameters params) {
                SSLContext c = getSSLContext();
                SSLEngine engine = c.createSSLEngine();
                params.setNeedClientAuth(false);
                params.setCipherSuites(engine.getEnabledCipherSuites());
                params.setProtocols(engine.getEnabledProtocols());
                SSLParameters defaultParams = c.getDefaultSSLParameters();
                params.setSSLParameters(defaultParams);
            }
        });
        return https;
    }
}
