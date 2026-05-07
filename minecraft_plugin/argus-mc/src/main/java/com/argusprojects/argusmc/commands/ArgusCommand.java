package com.argusprojects.argusmc.commands;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.api.HealthResponse;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.TabCompleter;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Comando /argus &lt;reload|info|test&gt;
 *
 * Solo visible para staff con permiso 'argus.admin'.
 */
public final class ArgusCommand implements CommandExecutor, TabCompleter {

    private static final List<String> SUBS = Arrays.asList("reload", "info", "test");

    private final ArgusPlugin plugin;

    public ArgusCommand(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        if (!sender.hasPermission("argus.admin")) {
            plugin.getMessages().sendPrefixed(sender, "no_permission", null);
            return true;
        }
        Messages msg = plugin.getMessages();

        if (args.length == 0) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/argus <reload|info|test>"));
            return true;
        }

        String sub = args[0].toLowerCase();
        switch (sub) {
            case "reload": handleReload(sender); break;
            case "info":   handleInfo(sender);   break;
            case "test":   handleTest(sender);   break;
            default:
                sender.sendMessage(msg.prefix() + Messages.color("&cSubcomando desconocido: &f" + sub));
                break;
        }
        return true;
    }

    private void handleReload(CommandSender sender) {
        Messages msg = plugin.getMessages();
        try {
            plugin.reloadConfigState();
            msg.sendPrefixed(sender, "argus_reload_ok", null);
        } catch (Exception ex) {
            msg.sendPrefixed(sender, "argus_reload_fail",
                Messages.ph("error", ex.getMessage()));
        }
    }

    private void handleInfo(CommandSender sender) {
        Messages msg = plugin.getMessages();
        sender.sendMessage(msg.prefix() + Messages.color("&7Consultando estado..."));

        plugin.getApiClient().healthCheckAsync().whenComplete((resp, err) -> {
            Bukkit.getScheduler().runTask(plugin, () -> {
                String status, company, used, quota;
                String endpoint = plugin.getArgusConfig().getBaseUrl() + "/api/plugin/health";

                if (err != null || resp == null || !resp.success) {
                    status = Messages.color("&cdesconectado");
                    company = "—";
                    used = "?"; quota = "?";
                } else if (!resp.authenticated) {
                    status = Messages.color("&cAPI key invalida");
                    company = "—";
                    used = "?"; quota = "?";
                } else {
                    status = Messages.color("&aok (" + (resp.status != null ? resp.status : "active") + ")");
                    company = resp.label != null && !resp.label.isEmpty()
                        ? resp.label
                        : ("ID " + resp.companyId);
                    used  = resp.usedToday  != null ? String.valueOf(resp.usedToday)  : "?";
                    quota = resp.dailyQuota != null ? String.valueOf(resp.dailyQuota) : "?";
                }

                msg.send(sender, "argus_info", Messages.ph(
                    "version", plugin.getDescription().getVersion(),
                    "endpoint", endpoint,
                    "status", status,
                    "company", company,
                    "used", used,
                    "quota", quota
                ));
            });
        });
    }

    private void handleTest(CommandSender sender) {
        Messages msg = plugin.getMessages();
        if (plugin.getArgusConfig().isMisconfigured()) {
            msg.sendPrefixed(sender, "api_misconfigured", null);
            return;
        }
        sender.sendMessage(msg.prefix() + Messages.color("&7Probando conexion con Argus..."));
        plugin.getApiClient().healthCheckAsync().whenComplete((resp, err) -> {
            Bukkit.getScheduler().runTask(plugin, () -> {
                if (err != null) {
                    sender.sendMessage(msg.prefix() + Messages.color("&cError de red: &f" + err.getMessage()));
                    return;
                }
                if (resp == null || !resp.success) {
                    String e = resp != null ? resp.errorMessage : "respuesta vacia";
                    sender.sendMessage(msg.prefix() + Messages.color("&cFallo: &f" + e));
                    return;
                }
                if (!resp.authenticated) {
                    sender.sendMessage(msg.prefix() + Messages.color("&cConexion OK pero la API key no es valida."));
                    return;
                }
                sender.sendMessage(msg.prefix() + Messages.color(
                    "&aTodo OK. &7Empresa #" + resp.companyId
                    + " (" + (resp.label != null ? resp.label : "sin label") + ") · "
                    + resp.usedToday + "/" + resp.dailyQuota + " emisiones hoy."));
            });
        });
    }

    @Override
    public List<String> onTabComplete(CommandSender sender, Command command, String alias, String[] args) {
        if (args.length == 1) {
            List<String> out = new ArrayList<>();
            String partial = args[0].toLowerCase();
            for (String s : SUBS) {
                if (s.startsWith(partial)) out.add(s);
            }
            return out;
        }
        return new ArrayList<>();
    }
}
