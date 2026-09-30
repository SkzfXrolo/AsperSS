package com.argusprojects.argusmc.anticheat;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.api.ArgusApiClient;
import com.argusprojects.argusmc.service.SsService;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.BanList;
import org.bukkit.Bukkit;
import org.bukkit.ChatColor;
import org.bukkit.entity.Player;

import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Date;
import java.util.Deque;
import java.util.HashSet;
import java.util.Iterator;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.atomic.AtomicLong;
import java.util.logging.Level;

public final class ViolationManager {

    private final ArgusPlugin plugin;
    private final SsService ssService;

    private final Map<UUID, Deque<Violation>> recent = new ConcurrentHashMap<>();

    private static final int GLOBAL_RING_SIZE = 200;
    private final Deque<Violation> globalRecent = new ArrayDeque<>();

    private final Map<String, AtomicLong> totalByCheck = new ConcurrentHashMap<>();
    private final Map<String, AtomicLong> totalByLevel = new ConcurrentHashMap<>();

    private final Set<UUID> pendingForcedSs = ConcurrentHashMap.newKeySet();

    private final Map<UUID, Map<String, Long>> lastStaffAlertMs = new ConcurrentHashMap<>();
    private static final long STAFF_ALERT_COOLDOWN_MS = 3_000L;

    public ViolationManager(ArgusPlugin plugin) {
        this.plugin = plugin;
        this.ssService = new SsService(plugin);
    }

    public List<Violation> snapshotGlobalRecent(int limit) {
        synchronized (globalRecent) {
            List<Violation> out = new ArrayList<>(globalRecent);
            if (limit > 0 && out.size() > limit) {
                return out.subList(out.size() - limit, out.size());
            }
            return out;
        }
    }

    public Map<String, AtomicLong> totalByCheck() { return totalByCheck; }

    public Map<String, AtomicLong> totalByLevel() { return totalByLevel; }

    public void flag(Violation v) {
        if (v == null) return;
        AnticheatConfig cfg = plugin.getAnticheatConfig();
        if (cfg == null || !cfg.isEnabled()) return;

        Player player = Bukkit.getPlayer(v.playerUuid);
        if (player == null) return;
        if (player.hasPermission("argus.ac.bypass")) return;

        v = applyLevelOverride(v, cfg);

        synchronized (globalRecent) {
            globalRecent.addLast(v);
            while (globalRecent.size() > GLOBAL_RING_SIZE) globalRecent.pollFirst();
        }
        totalByCheck.computeIfAbsent(v.checkName, k -> new AtomicLong())
            .incrementAndGet();
        totalByLevel.computeIfAbsent(v.level.name(), k -> new AtomicLong())
            .incrementAndGet();

        Deque<Violation> queue = recent.computeIfAbsent(v.playerUuid, k -> new ArrayDeque<>());
        synchronized (queue) {
            long cutoff = System.currentTimeMillis() - (cfg.getViolationWindowSeconds() * 1000L);
            while (!queue.isEmpty() && queue.peekFirst().timestampMs < cutoff) {
                queue.pollFirst();
            }
            queue.addLast(v);
        }

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

        if (critical >= cfg.getCriticalBanAt()) {
            handleCritical(player, v, cfg);
        } else if (high >= cfg.getHighForceSs()) {
            handleHigh(player, v, cfg);
        } else if (mid >= cfg.getMidKickAt()) {
            handleMid(player, v, cfg);
        } else if (low >= cfg.getLowAlertAt()) {
            handleLow(player, v, cfg);
        }

        if (cfg.isReportToBackendForCheck(v.checkName)) {
            reportToBackendAsync(v);
        }
        if (cfg.isDiscordForCheck(v.checkName) && v.level.atLeast(ViolationLevel.MID)) {
            sendDiscordWebhookAsync(v, cfg.getDiscordWebhookUrl());
        }

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

    private void handleAiVerdict(Player player, Violation v, AiVerdict verdict, String localAction) {
        if (player == null || !player.isOnline()) return;
        AnticheatConfig cfg = plugin.getAnticheatConfig();

        String aiAction     = verdict.mergedAction != null ? verdict.mergedAction : verdict.action;
        if (aiAction == null) aiAction = "none";

        String prefix = "&8[&b&lArgus AI&8] &7";
        String header = String.format("%s%s &8(score &f%.2f&8 conf &f%.2f&8) &b%s &8>",
            prefix, player.getName(), verdict.score, verdict.confidence, aiAction.toUpperCase());
        String header2 = "  &7" + (verdict.reasoning == null ? "(sin reasoning)" : verdict.reasoning);

        for (Player op : Bukkit.getOnlinePlayers()) {
            if (op.hasPermission("argus.alerts")) {
                op.sendMessage(ChatColor.translateAlternateColorCodes('&', header));
                op.sendMessage(ChatColor.translateAlternateColorCodes('&', header2));
            }
        }
        Bukkit.getConsoleSender().sendMessage(
            ChatColor.translateAlternateColorCodes('&',
                "[ArgusAI] " + player.getName() + " score=" + verdict.score
                    + " action=" + aiAction + " | " + verdict.reasoning));

        int rankLocal = actionRank(localAction);
        int rankAi    = actionRank(aiAction);
        if (rankAi <= rankLocal) return;

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

    private boolean canEnforce(AnticheatConfig cfg, Violation v, String desiredAction) {
        if (!cfg.isEnforcementForCheck(v.checkName)) return false;
        String cap = cfg.actionCapForCheck(v.checkName);
        if (cap == null) return true;
        return actionRank(desiredAction) <= actionRank(cap);
    }

    private void broadcastStaffAlert(String msgKey, Violation v) {
        if (!shouldStaffAlert(v.playerUuid, v.checkName)) return;

        String line = ViolationFormatter.staffLine(v);
        String colored = Messages.color(line);
        for (Player online : Bukkit.getOnlinePlayers()) {
            if (online.hasPermission("argus.alerts")) {
                online.sendMessage(colored);
            }
        }
        Bukkit.getConsoleSender().sendMessage(colored);

        try {
            var bootstrap = plugin.getPacketEventsBootstrap();
            if (bootstrap != null && bootstrap.getDataStore() != null) {
                var s = bootstrap.getDataStore().peek(v.playerUuid);
                if (s != null && s.watchedBy != null) {
                    Player watcher = Bukkit.getPlayer(s.watchedBy);
                    if (watcher != null && watcher.isOnline()) {
                        watcher.sendMessage(Messages.color("&8[&b&lWATCH&8] &f" + v.playerName
                            + " &7| &f" + ViolationFormatter.checkLabel(v.checkName)
                            + "&7: " + ViolationFormatter.formatSummary(v.checkName, v.details)));
                    }
                }
            }
        } catch (Throwable ignored) {}
    }

    private boolean shouldStaffAlert(UUID playerUuid, String checkName) {
        long now = System.currentTimeMillis();
        Map<String, Long> perCheck = lastStaffAlertMs.computeIfAbsent(playerUuid, k -> new ConcurrentHashMap<>());
        Long last = perCheck.get(checkName);
        if (last != null && now - last < STAFF_ALERT_COOLDOWN_MS) return false;
        perCheck.put(checkName, now);
        return true;
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

    public boolean hasPendingForcedSs(UUID uuid) {
        return pendingForcedSs.contains(uuid);
    }

    public void consumePendingForcedSs(Player player) {
        if (pendingForcedSs.remove(player.getUniqueId())) {

            Bukkit.getScheduler().runTaskLater(plugin, () -> {
                if (player.isOnline()) {
                    ssService.issueScreenShare(
                        Bukkit.getConsoleSender(),
                        player.getName(),
                        "auto-SS por anti-cheat (HIGH)",
                        SsService.Source.ANTICHEAT_AUTO
                    );
                }
            }, 60L);
        }
    }

    public void clearViolations(UUID uuid) {
        recent.remove(uuid);
    }

    public void onPlayerQuit(UUID uuid) {

    }

    public int countRecent(UUID uuid) {
        Deque<Violation> q = recent.get(uuid);
        if (q == null) return 0;
        synchronized (q) {

            long cutoff = System.currentTimeMillis() - (plugin.getAnticheatConfig().getViolationWindowSeconds() * 1000L);
            int count = 0;
            for (Iterator<Violation> it = q.iterator(); it.hasNext(); ) {
                if (it.next().timestampMs >= cutoff) count++;
            }
            return count;
        }
    }
}
