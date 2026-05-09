package com.argusprojects.argusmc.anticheat;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.api.ArgusApiClient;
import com.argusprojects.argusmc.service.SsService;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.BanList;
import org.bukkit.Bukkit;
import org.bukkit.entity.Player;

import java.util.ArrayDeque;
import java.util.Date;
import java.util.Deque;
import java.util.HashSet;
import java.util.Iterator;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.logging.Level;

/**
 * Cerebro del anti-cheat.
 *
 * <p>Recibe {@link Violation}s de los checks individuales (que viven como
 * Listener separados), las acumula en una sliding window por jugador, y
 * decide la accion segun su {@link ViolationLevel}:
 *
 * <ul>
 *   <li>LOW       → alerta in-game al staff con permiso 'argus.alerts'.</li>
 *   <li>MID       → kick + alerta + Discord.</li>
 *   <li>HIGH      → kick + auto-emision de SS al reconectar + Discord.</li>
 *   <li>CRITICAL  → ban temporal + alerta urgente + Discord.</li>
 * </ul>
 *
 * <p>Si <code>anticheat.enforcement = false</code> en config, NUNCA kickea
 * ni banea — solo loguea y alerta. Util para los primeros dias en un
 * server nuevo (modo observador).
 *
 * <p>Es thread-safe (usa {@link ConcurrentHashMap}) porque varios listeners
 * pueden flagear simultaneamente.
 */
public final class ViolationManager {

    private final ArgusPlugin plugin;
    private final SsService ssService;

    /** Cola de violations recientes por jugador (sliding window). */
    private final Map<UUID, Deque<Violation>> recent = new ConcurrentHashMap<>();

    /** Jugadores que tienen un SS forzado pendiente al reconectar. */
    private final Set<UUID> pendingForcedSs = ConcurrentHashMap.newKeySet();

    public ViolationManager(ArgusPlugin plugin) {
        this.plugin = plugin;
        this.ssService = new SsService(plugin);
    }

    /**
     * Reporta una violation. La unica entrada publica del sistema.
     * Puede llamarse desde cualquier thread (es thread-safe).
     */
    public void flag(Violation v) {
        if (v == null) return;
        AnticheatConfig cfg = plugin.getAnticheatConfig();
        if (cfg == null || !cfg.isEnabled()) return;

        Player player = Bukkit.getPlayer(v.playerUuid);
        if (player == null) return;
        if (player.hasPermission("argus.ac.bypass")) return;

        // 1) Acumular en la cola y limpiar las viejas
        Deque<Violation> queue = recent.computeIfAbsent(v.playerUuid, k -> new ArrayDeque<>());
        synchronized (queue) {
            long cutoff = System.currentTimeMillis() - (cfg.getViolationWindowSeconds() * 1000L);
            while (!queue.isEmpty() && queue.peekFirst().timestampMs < cutoff) {
                queue.pollFirst();
            }
            queue.addLast(v);
        }

        // 2) Contar por nivel en la ventana actual
        int low = 0, mid = 0, high = 0, critical = 0;
        synchronized (queue) {
            for (Violation past : queue) {
                switch (past.level) {
                    case LOW:      low++;      break;
                    case MID:      mid++;      break;
                    case HIGH:     high++;     break;
                    case CRITICAL: critical++; break;
                }
            }
        }

        // 3) Decidir accion (de mayor a menor severidad)
        if (critical >= cfg.getCriticalBanAt()) {
            handleCritical(player, v, cfg);
        } else if (high >= cfg.getHighForceSs()) {
            handleHigh(player, v, cfg);
        } else if (mid >= cfg.getMidKickAt()) {
            handleMid(player, v, cfg);
        } else if (low >= cfg.getLowAlertAt()) {
            handleLow(player, v, cfg);
        }

        // 4) Reportar al backend y Discord (siempre, no solo cuando se aplica accion)
        if (cfg.isReportToBackend()) {
            reportToBackendAsync(v);
        }
        if (cfg.hasDiscordWebhook() && v.level.atLeast(ViolationLevel.MID)) {
            sendDiscordWebhookAsync(v, cfg.getDiscordWebhookUrl());
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Manejadores por nivel
    // ──────────────────────────────────────────────────────────────────────

    private void handleLow(Player player, Violation v, AnticheatConfig cfg) {
        broadcastStaffAlert("ac_alert_low", v);
        plugin.getLogger().fine(() -> "[AC] LOW " + v);
    }

    private void handleMid(Player player, Violation v, AnticheatConfig cfg) {
        broadcastStaffAlert("ac_alert_mid", v);
        plugin.getLogger().info("[AC] MID kick: " + v);
        if (cfg.isEnforcement()) {
            kickPlayer(player, v, "ac_kick_message");
            clearViolations(player.getUniqueId());
        }
    }

    private void handleHigh(Player player, Violation v, AnticheatConfig cfg) {
        broadcastStaffAlert("ac_alert_high", v);
        plugin.getLogger().warning("[AC] HIGH kick + force-SS: " + v);
        if (cfg.isEnforcement()) {
            pendingForcedSs.add(player.getUniqueId());
            kickPlayer(player, v, "ac_kick_message");
            clearViolations(player.getUniqueId());
        }
    }

    private void handleCritical(Player player, Violation v, AnticheatConfig cfg) {
        broadcastStaffAlert("ac_alert_critical", v);
        plugin.getLogger().severe("[AC] CRITICAL ban: " + v);
        if (cfg.isEnforcement()) {
            banPlayerTemporarily(player, v, cfg.getCriticalBanMinutes());
            clearViolations(player.getUniqueId());
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Acciones primitivas
    // ──────────────────────────────────────────────────────────────────────

    private void broadcastStaffAlert(String msgKey, Violation v) {
        Messages msg = plugin.getMessages();
        Map<String, String> ph = Messages.ph(
            "player",  v.playerName,
            "check",   v.checkName,
            "details", v.details,
            "level",   v.level.name()
        );
        String text = msg.get(msgKey, ph);
        for (Player online : Bukkit.getOnlinePlayers()) {
            if (online.hasPermission("argus.alerts")) {
                online.sendMessage(text);
            }
        }
        Bukkit.getConsoleSender().sendMessage(text);
    }

    private void kickPlayer(Player player, Violation v, String msgKey) {
        Bukkit.getScheduler().runTask(plugin, () -> {
            String kickMsg = plugin.getMessages().get(msgKey, Messages.ph(
                "check",   v.checkName,
                "details", v.details
            ));
            try {
                player.kickPlayer(kickMsg);
            } catch (Exception ex) {
                plugin.getLogger().log(Level.WARNING, "Error kickeando a " + player.getName() + ": " + ex.getMessage());
            }
        });
    }

    @SuppressWarnings("deprecation")
    private void banPlayerTemporarily(Player player, Violation v, int minutes) {
        Bukkit.getScheduler().runTask(plugin, () -> {
            try {
                Date expires = new Date(System.currentTimeMillis() + (minutes * 60_000L));
                String reason = "[ArgusAC] " + v.checkName + " (" + v.details + ")";
                Bukkit.getBanList(BanList.Type.NAME).addBan(player.getName(), reason, expires, "ArgusAC");
                String kickMsg = plugin.getMessages().get("ac_ban_message", Messages.ph(
                    "check",   v.checkName,
                    "details", v.details,
                    "minutes", String.valueOf(minutes)
                ));
                player.kickPlayer(kickMsg);
            } catch (Exception ex) {
                plugin.getLogger().log(Level.WARNING, "Error baneando a " + player.getName() + ": " + ex.getMessage());
            }
        });
    }

    private void reportToBackendAsync(Violation v) {
        ArgusApiClient client = plugin.getApiClient();
        if (client == null) return;
        if (plugin.getArgusConfig().isMisconfigured()) return;
        client.reportViolationAsync(v);
    }

    private void sendDiscordWebhookAsync(Violation v, String webhookUrl) {
        ArgusApiClient client = plugin.getApiClient();
        if (client == null) return;
        client.sendDiscordWebhookAsync(webhookUrl, v);
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Auto-SS forzado al reconectar
    // ──────────────────────────────────────────────────────────────────────

    /** Llamado por AnticheatListener#onJoin. */
    public boolean hasPendingForcedSs(UUID uuid) {
        return pendingForcedSs.contains(uuid);
    }

    public void consumePendingForcedSs(Player player) {
        if (pendingForcedSs.remove(player.getUniqueId())) {
            // Pequeña espera para que termine de cargar el chunk
            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (player.isOnline()) {
                    ssService.issueScreenShare(
                        Bukkit.getConsoleSender(),
                        player.getName(),
                        "auto-SS por anti-cheat (HIGH)",
                        SsService.Source.ANTICHEAT_AUTO
                    );
                }
            }, 60L); // 3 segundos
        }
    }

    public void clearViolations(UUID uuid) {
        recent.remove(uuid);
    }

    public void onPlayerQuit(UUID uuid) {
        // No limpiamos la cola: si reconecta dentro de la window, sus violations cuentan.
        // Solo limpiamos al hacer kick/ban (efecto deliberado).
        // Si quieres limpiar al quit, descomentar:
        // recent.remove(uuid);
    }

    /** Util para debug / status. */
    public int countRecent(UUID uuid) {
        Deque<Violation> q = recent.get(uuid);
        if (q == null) return 0;
        synchronized (q) {
            // Filtrar por window al vuelo
            long cutoff = System.currentTimeMillis() - (plugin.getAnticheatConfig().getViolationWindowSeconds() * 1000L);
            int count = 0;
            for (Iterator<Violation> it = q.iterator(); it.hasNext(); ) {
                if (it.next().timestampMs >= cutoff) count++;
            }
            return count;
        }
    }
}
