package com.argusprojects.argusmc.commands;

import com.argusprojects.argusmc.ArgusConfig;
import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.api.TokenResponse;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * Comando /ss &lt;player&gt; [reason]
 *
 * Flow:
 *  1. Valida permisos (LuckyPerms-friendly via Bukkit#hasPermission).
 *  2. Valida que el target exista y no este bypassed.
 *  3. Llama async al backend para emitir un token.
 *  4. Notifica staff (siempre) y target (si notify_target = true).
 *  5. Broadcast opcional a otros staff con argus.ss.notify.
 */
public final class SsCommand implements CommandExecutor, TabCompleter {

    private final ArgusPlugin plugin;

    public SsCommand(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        Messages msg = plugin.getMessages();

        if (!sender.hasPermission("argus.ss.use")) {
            msg.sendPrefixed(sender, "no_permission", null);
            return true;
        }
        ArgusConfig cfg = plugin.getArgusConfig();
        if (cfg.isMisconfigured()) {
            msg.sendPrefixed(sender, "api_misconfigured", null);
            return true;
        }

        if (args.length < 1) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/ss <player> [razon]"));
            return true;
        }

        String targetName = args[0];

        // Razon = argumentos siguientes unidos
        String reason = "";
        if (args.length > 1) {
            StringBuilder sb = new StringBuilder();
            for (int i = 1; i < args.length; i++) {
                if (i > 1) sb.append(' ');
                sb.append(args[i]);
            }
            reason = sb.toString().trim();
        }
        if (cfg.isRequireReason() && reason.length() < cfg.getMinReasonLength()) {
            msg.sendPrefixed(sender, "reason_too_short",
                Messages.ph("min", String.valueOf(cfg.getMinReasonLength())));
            return true;
        }

        // Auto-target invalido
        if (sender instanceof Player p && p.getName().equalsIgnoreCase(targetName)) {
            msg.sendPrefixed(sender, "cannot_target_self", null);
            return true;
        }

        Player target = Bukkit.getPlayerExact(targetName);
        if (target == null) {
            msg.sendPrefixed(sender, "player_not_found", Messages.ph("player", targetName));
            return true;
        }
        if (target.hasPermission("argus.ss.bypass")) {
            msg.sendPrefixed(sender, "player_is_bypassed", null);
            return true;
        }

        String staffName = sender instanceof Player p ? p.getName() : "console";
        String finalReason = reason.isEmpty() ? "(sin razon)" : reason;

        // Llamada async — no bloqueamos el hilo principal del server
        sender.sendMessage(msg.prefix() + Messages.color("&7Solicitando codigo a Argus..."));

        plugin.getApiClient()
            .issueTokenAsync(staffName, target.getName(), reason)
            .whenComplete((resp, err) -> {
                Bukkit.getScheduler().runTask(plugin, () -> handleResponse(sender, target, staffName, finalReason, resp, err));
            });
        return true;
    }

    private void handleResponse(CommandSender sender, Player target, String staffName, String reason,
                                TokenResponse resp, Throwable err) {
        Messages msg = plugin.getMessages();

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
            : (plugin.getArgusConfig().getBaseUrl() + "/descargar/exe");
        Map<String, String> staffPh = Messages.ph(
            "code", resp.shortCode,
            "target", target.getName(),
            "download", download
        );
        msg.send(sender, "ss_issued_staff", staffPh);

        if (plugin.getArgusConfig().isNotifyTarget() && target.isOnline()) {
            Map<String, String> targetPh = Messages.ph(
                "code", resp.shortCode,
                "staff", staffName,
                "reason", reason,
                "download", download
            );
            msg.send(target, "ss_issued_target", targetPh);
        }

        if (plugin.getArgusConfig().isBroadcastToStaff()) {
            String announce = msg.get("ss_broadcast_staff",
                Messages.ph("staff", staffName, "target", target.getName(), "reason", reason));
            for (Player online : Bukkit.getOnlinePlayers()) {
                if (online.hasPermission("argus.ss.notify")) {
                    online.sendMessage(announce);
                }
            }
        }

        plugin.getLogger().info(String.format(
            "[/ss] %s -> %s | code=%s reason=%s",
            staffName, target.getName(), resp.shortCode, reason
        ));
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1 && sender.hasPermission("argus.ss.use")) {
            String partial = args[0].toLowerCase();
            List<String> matches = new ArrayList<>();
            for (Player p : Bukkit.getOnlinePlayers()) {
                if (p.getName().toLowerCase().startsWith(partial)) {
                    matches.add(p.getName());
                }
            }
            return matches;
        }
        return new ArrayList<>();
    }
}
