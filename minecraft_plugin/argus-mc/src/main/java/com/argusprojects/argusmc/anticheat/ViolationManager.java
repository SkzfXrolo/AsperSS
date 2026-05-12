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

    /** Ring buffer global de las ultimas N violations (Pack 48 round 2 — Web Dashboard). */
    private static final int GLOBAL_RING_SIZE = 200;
    private final Deque<Violation> globalRecent = new ArrayDeque<>();

    /** Counters acumulados para /metrics Prometheus. */
    private final Map<String, java.util.concurrent.atomic.AtomicLong> totalByCheck = new ConcurrentHashMap<>();
    private final Map<String, java.util.concurrent.atomic.AtomicLong> totalByLevel = new ConcurrentHashMap<>();

    /** Jugadores que tienen un SS forzado pendiente al reconectar. */
    private final Set<UUID> pendingForcedSs = ConcurrentHashMap.newKeySet();

    public ViolationManager(ArgusPlugin plugin) {
        this.plugin = plugin;
        this.ssService = new SsService(plugin);
    }

    /** Snapshot del ring buffer global (Pack 48 round 2 — Web Dashboard). */
    public java.util.List<Violation> snapshotGlobalRecent(int limit) {
        synchronized (globalRecent) {
            java.util.List<Violation> out = new java.util.ArrayList<>(globalRecent);
            if (limit > 0 && out.size() > limit) {
                return out.subList(out.size() - limit, out.size());
            }
            return out;
        }
    }

    /** Counters por check name (para Prometheus). */
    public Map<String, java.util.concurrent.atomic.AtomicLong> totalByCheck() { return totalByCheck; }

    /** Counters por level (para Prometheus). */
    public Map<String, java.util.concurrent.atomic.AtomicLong> totalByLevel() { return totalByLevel; }

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

        // Pack 48 #525 — Per-check level override.
        v = applyLevelOverride(v, cfg);

        // Round 2 — feed ring buffer global + counters Prometheus.
        synchronized (globalRecent) {
            globalRecent.addLast(v);
            while (globalRecent.size() > GLOBAL_RING_SIZE) globalRecent.pollFirst();
        }
        totalByCheck.computeIfAbsent(v.checkName, k -> new java.util.concurrent.atomic.AtomicLong())
            .incrementAndGet();
        totalByLevel.computeIfAbsent(v.level.name(), k -> new java.util.concurrent.atomic.AtomicLong())
            .incrementAndGet();

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

        // 4) Reportar al backend y Discord. Pack 48 #522/#523: respeta flags per-check.
        if (cfg.isReportToBackendForCheck(v.checkName)) {
            reportToBackendAsync(v);
        }
        if (cfg.isDiscordForCheck(v.checkName) && v.level.atLeast(ViolationLevel.MID)) {
            sendDiscordWebhookAsync(v, cfg.getDiscordWebhookUrl());
        }

        // 5) Pack 44 + Pack 48 #524: AI Oracle si globalmente habilitado Y el
        // check no tiene ai_oracle: false explicito. Si el plugin local ya
        // kickeo/baneo, esto solo escala (nunca menos).
        if (cfg.isAiOracleForCheck(v.checkName)) {
            final Violation finalV = v;
            String localAction = decideLocalAction(low, mid, high, critical, cfg);
            plugin.getApiClient().evaluateAiAsync(finalV, localAction)
                .whenComplete((verdict, err) -> {
                    if (verdict == null) return;
                    Bukkit.getScheduler().runTask(plugin,
                        () -> handleAiVerdict(player, finalV, verdict, localAction));
                });
        }
    }

    /** Pack 48 #525 — applies the per-check level override (if any). */
    private Violation applyLevelOverride(Violation v, AnticheatConfig cfg) {
        ViolationLevel forced = cfg.levelOverrideForCheck(v.checkName);
        if (forced == null) return v;
        return v.withLevel(forced);
    }

    private String decideLocalAction(int low, int mid, int high, int critical, AnticheatConfig cfg) {
        if (critical >= cfg.getCriticalBanAt()) return "ban";
        if (high >= cfg.getHighForceSs())       return "kick";
        if (mid >= cfg.getMidKickAt())          return "kick";
        if (low >= cfg.getLowAlertAt())         return "watch";
        return "none";
    }

    /**
     * El Oracle devolvio un veredicto. Si pide una accion MAS SEVERA que la
     * que el plugin local tomo, la aplicamos y avisamos al staff con el
     * reasoning humanizado del Oracle (es lo mas potente del feature: el
     * staff recibe un mensaje tipo "Cheater confirmado, ban temporal" en
     * vez de "[AC] HIGH player_name -> killaura_no_swing").
     */
    private void handleAiVerdict(Player player, Violation v, AiVerdict verdict, String localAction) {
        if (player == null || !player.isOnline()) return;
        AnticheatConfig cfg = plugin.getAnticheatConfig();

        String aiAction     = verdict.mergedAction != null ? verdict.mergedAction : verdict.action;
        if (aiAction == null) aiAction = "none";

        // Broadcast del reasoning humanizado a staff con argus.alerts.
        // Esto es lo que hace que la "voz" del Oracle se sienta.
        String prefix = "&8[&b&lArgus AI&8] &7";
        String header = String.format("%s%s &8(score &f%.2f&8 conf &f%.2f&8) &b%s &8>",
            prefix, player.getName(), verdict.score, verdict.confidence, aiAction.toUpperCase());
        String header2 = "  &7" + (verdict.reasoning == null ? "(sin reasoning)" : verdict.reasoning);

        for (Player op : Bukkit.getOnlinePlayers()) {
            if (op.hasPermission("argus.alerts")) {
                op.sendMessage(org.bukkit.ChatColor.translateAlternateColorCodes('&', header));
                op.sendMessage(org.bukkit.ChatColor.translateAlternateColorCodes('&', header2));
            }
        }
        Bukkit.getConsoleSender().sendMessage(
            org.bukkit.ChatColor.translateAlternateColorCodes('&',
                "[ArgusAI] " + player.getName() + " score=" + verdict.score
                    + " action=" + aiAction + " | " + verdict.reasoning));

        // Solo aplicamos si la accion de la AI es MAS severa que la local.
        // El plugin ya hizo la accion local; la AI solo escala.
        int rankLocal = actionRank(localAction);
        int rankAi    = actionRank(aiAction);
        if (rankAi <= rankLocal) return;
        // Pack 48 #521 + #526 — respeta per-check enforce y action cap.
        if (!canEnforce(cfg, v, aiAction)) return;

        switch (aiAction) {
            case "ban":
                plugin.getLogger().warning("[AI] Escalando a BAN: " + player.getName() + " — " + verdict.reasoning);
                banPlayerTemporarily(player, v, cfg.getCriticalBanMinutes());
                break;
            case "kick":
                plugin.getLogger().info("[AI] Escalando a KICK: " + player.getName() + " — " + verdict.reasoning);
                pendingForcedSs.add(player.getUniqueId());
                kickPlayer(player, v, "ac_kick_message");
                break;
            case "ss":
                plugin.getLogger().info("[AI] Forzando SS: " + player.getName());
                ssService.issueScreenShare(
                    Bukkit.getConsoleSender(), player.getName(),
                    "Argus AI Oracle: " + (verdict.topFactor != null ? verdict.topFactor : "sospecha alta"),
                    SsService.Source.ANTICHEAT_AUTO);
                break;
            case "watch":
                // Solo log + alerta. Nada que hacer en el cliente.
                break;
        }
    }

    private static int actionRank(String a) {
        if (a == null) return 0;
        switch (a.toLowerCase()) {
            case "watch": return 1;
            case "ss":    return 2;
            case "kick":  return 3;
            case "ban":   return 4;
            default:      return 0;
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
        if (!canEnforce(cfg, v, "kick")) return;
        kickPlayer(player, v, "ac_kick_message");
        clearViolations(player.getUniqueId());
    }

    private void handleHigh(Player player, Violation v, AnticheatConfig cfg) {
        broadcastStaffAlert("ac_alert_high", v);
        plugin.getLogger().warning("[AC] HIGH kick + force-SS: " + v);
        if (!canEnforce(cfg, v, "kick")) return;
        pendingForcedSs.add(player.getUniqueId());
        kickPlayer(player, v, "ac_kick_message");
        clearViolations(player.getUniqueId());
    }

    private void handleCritical(Player player, Violation v, AnticheatConfig cfg) {
        broadcastStaffAlert("ac_alert_critical", v);
        plugin.getLogger().severe("[AC] CRITICAL ban: " + v);
        if (!canEnforce(cfg, v, "ban")) return;
        banPlayerTemporarily(player, v, cfg.getCriticalBanMinutes());
        clearViolations(player.getUniqueId());
    }

    /**
     * Pack 48 #521 + #526 — Verifica si una accion concreta puede ejecutarse.
     * Combina dos overrides:
     * <ul>
     *   <li>#521 per-check enforce flag (si false, ningun enforcement).</li>
     *   <li>#526 per-check max_action cap (si la accion solicitada supera
     *       el cap, no se ejecuta).</li>
     * </ul>
     */
    private boolean canEnforce(AnticheatConfig cfg, Violation v, String desiredAction) {
        if (!cfg.isEnforcementForCheck(v.checkName)) return false;
        String cap = cfg.actionCapForCheck(v.checkName);
        if (cap == null) return true;
        return actionRank(desiredAction) <= actionRank(cap);
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

        // /argus admin watch — feed VERBOSO al admin que esta observando.
        try {
            var bootstrap = plugin.getPacketEventsBootstrap();
            if (bootstrap != null && bootstrap.getDataStore() != null) {
                var s = bootstrap.getDataStore().peek(v.playerUuid);
                if (s != null && s.watchedBy != null) {
                    Player watcher = Bukkit.getPlayer(s.watchedBy);
                    if (watcher != null && watcher.isOnline()) {
                        watcher.sendMessage("§8[§b§lWATCH§8] §f" + v.playerName
                            + " §7" + v.checkName + " §8(§7" + v.level.name() + "§8) §8" + v.details);
                    }
                }
            }
        } catch (Throwable ignored) {}
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
        // Pack 48 round 2: si hay ViolationBuffer activo, enviamos por ahi
        // (batched + back-pressure). Si no, fallback directo.
        var buf = plugin.getViolationBuffer();
        if (buf != null) {
            buf.offer(v);
        } else {
            client.reportViolationAsync(v);
        }
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
