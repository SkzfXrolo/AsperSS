package com.argusprojects.argusmc.service;

import com.argusprojects.argusmc.ArgusConfig;
import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.api.TokenResponse;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.Bukkit;
import org.bukkit.command.CommandSender;
import org.bukkit.entity.Player;

import java.util.Map;

/**
 * Servicio reutilizable que ejecuta el flujo de Screen Share.
 *
 * <p>Antes vivia dentro de SsCommand, pero al renombrar el comando top-level
 * /ss → /argus check (para evitar colisiones con otros plugins, ej. el /ss
 * de freeze de Arefy/Itzaru), extrajimos la logica a un servicio para poder
 * dispararla desde:
 *  - El subcomando /argus check (uso manual del staff)
 *  - El AntiCheatManager cuando un jugador supera N violations HIGH
 *    (auto-emision de SS forzado)
 *  - Cualquier otro origen interno futuro (API REST local, etc.)
 *
 * <p>Todas las operaciones bloqueantes se delegan al ArgusApiClient (que ya
 * usa CompletableFuture y un thread pool propio), por lo que este servicio
 * puede invocarse desde el hilo principal del server sin bloquear ticks.
 */
public final class SsService {

    public enum Source {
        STAFF_MANUAL,    // /argus check ejecutado por staff humano
        ANTICHEAT_AUTO,  // disparado por el sistema de violations
        CONSOLE          // ejecutado desde la consola del server
    }

    private final ArgusPlugin plugin;

    public SsService(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    /**
     * Ejecuta el flujo completo de SS.
     *
     * @param sender quien dispara el SS (puede ser CONSOLE o un Player con permiso)
     * @param targetName nombre MC del jugador objetivo
     * @param reason razon (puede ser null o vacia, salvo que require_reason=true)
     * @param source origen del trigger (afecta logging y mensajes)
     * @return true si el flujo arranco correctamente, false si fallo validacion
     *         sincrona (permisos, target inexistente, etc.). El resultado real
     *         de la API llega async y se entrega via mensajes en chat.
     */
    public boolean issueScreenShare(CommandSender sender, String targetName, String reason, Source source) {
        Messages msg = plugin.getMessages();
        ArgusConfig cfg = plugin.getArgusConfig();

        if (source == Source.STAFF_MANUAL && !sender.hasPermission("argus.ss.use")) {
            msg.sendPrefixed(sender, "no_permission", null);
            return false;
        }
        if (cfg.isMisconfigured()) {
            msg.sendPrefixed(sender, "api_misconfigured", null);
            return false;
        }
        if (targetName == null || targetName.isEmpty()) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/argus check <player> [razon]"));
            return false;
        }

        String finalReason = reason == null ? "" : reason.trim();
        if (source == Source.STAFF_MANUAL && cfg.isRequireReason() && finalReason.length() < cfg.getMinReasonLength()) {
            msg.sendPrefixed(sender, "reason_too_short",
                Messages.ph("min", String.valueOf(cfg.getMinReasonLength())));
            return false;
        }

        if (sender instanceof Player p && p.getName().equalsIgnoreCase(targetName)) {
            msg.sendPrefixed(sender, "cannot_target_self", null);
            return false;
        }

        Player target = Bukkit.getPlayerExact(targetName);
        if (target == null) {
            msg.sendPrefixed(sender, "player_not_found", Messages.ph("player", targetName));
            return false;
        }
        if (source != Source.ANTICHEAT_AUTO && target.hasPermission("argus.ss.bypass")) {
            // ANTICHEAT_AUTO ignora bypass: si el anticheat detecta cheats con altisima
            // confianza, ni los staff pueden esquivarlo (justo es justo).
            msg.sendPrefixed(sender, "player_is_bypassed", null);
            return false;
        }

        String staffName = sender instanceof Player p
            ? p.getName()
            : (source == Source.ANTICHEAT_AUTO ? "ArgusAC" : "console");
        String reasonForLog = finalReason.isEmpty()
            ? (source == Source.ANTICHEAT_AUTO ? "(auto-SS por anti-cheat)" : "(sin razon)")
            : finalReason;

        if (source != Source.ANTICHEAT_AUTO) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Solicitando codigo a Argus..."));
        }

        plugin.getApiClient()
            .issueTokenAsync(staffName, target.getName(), finalReason)
            .whenComplete((resp, err) -> Bukkit.getScheduler().runTask(plugin,
                () -> handleResponse(sender, target, staffName, reasonForLog, resp, err, source)));
        return true;
    }

    private void handleResponse(CommandSender sender, Player target, String staffName, String reason,
                                TokenResponse resp, Throwable err, Source source) {
        Messages msg = plugin.getMessages();
        ArgusConfig cfg = plugin.getArgusConfig();

        if (err != null) {
            msg.sendPrefixed(sender, "api_error", Messages.ph("error", err.getMessage()));
            return;
        }
        if (resp == null || !resp.success) {
            String e = resp != null ? resp.errorMessage : "respuesta vacia";
            msg.sendPrefixed(sender, "api_error", Messages.ph("error", e));
            return;
        }

        String download = resp.downloadUrl != null ? resp.downloadUrl
            : (cfg.getBaseUrl() + "/descargar/exe");
        Map<String, String> staffPh = Messages.ph(
            "code", resp.shortCode,
            "target", target.getName(),
            "download", download
        );
        msg.send(sender, "ss_issued_staff", staffPh);

        if (cfg.isNotifyTarget() && target.isOnline()) {
            Map<String, String> targetPh = Messages.ph(
                "code", resp.shortCode,
                "staff", staffName,
                "reason", reason,
                "download", download
            );
            msg.send(target, "ss_issued_target", targetPh);
        }

        if (cfg.isBroadcastToStaff()) {
            String announce = msg.get("ss_broadcast_staff",
                Messages.ph("staff", staffName, "target", target.getName(), "reason", reason));
            for (Player online : Bukkit.getOnlinePlayers()) {
                if (online.hasPermission("argus.ss.notify")) {
                    online.sendMessage(announce);
                }
            }
        }

        plugin.getLogger().info(String.format(
            "[/argus check] source=%s | %s -> %s | code=%s reason=%s",
            source, staffName, target.getName(), resp.shortCode, reason
        ));
    }
}
