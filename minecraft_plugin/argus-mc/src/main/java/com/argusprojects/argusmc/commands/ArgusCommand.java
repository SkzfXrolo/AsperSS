package com.argusprojects.argusmc.commands;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.api.HealthResponse;
import com.argusprojects.argusmc.service.SsService;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.Bukkit;
import org.bukkit.command.Command;
import org.bukkit.command.CommandExecutor;
import org.bukkit.command.CommandSender;
import org.bukkit.command.ConsoleCommandSender;
import org.bukkit.command.TabCompleter;
import org.bukkit.entity.Player;

import java.util.ArrayList;
import java.util.Arrays;
import java.util.List;

/**
 * Comando unificado /argus &lt;subcomando&gt;.
 *
 * <p>Subcomandos:
 * <ul>
 *   <li><b>check &lt;jugador&gt; [razon]</b> — emite token de Screen Share
 *       (reemplaza al viejo /ss para evitar choque con plugins de freeze).
 *       Aliases del subcomando: <code>ss</code>, <code>screenshare</code>,
 *       <code>scan</code>.</li>
 *   <li><b>reload</b> — recarga config.yml sin reiniciar.</li>
 *   <li><b>info</b> — muestra estado de conexion + quota.</li>
 *   <li><b>test</b> — health check rapido contra la API.</li>
 * </ul>
 *
 * <p>Permisos:
 * <ul>
 *   <li><code>argus.ss.use</code> → check</li>
 *   <li><code>argus.admin</code> → reload, info, test</li>
 * </ul>
 */
public final class ArgusCommand implements CommandExecutor, TabCompleter {

    private static final List<String> SS_ALIASES   = Arrays.asList("check", "ss", "screenshare", "scan");
    private static final List<String> ADMIN_SUBS   = Arrays.asList("reload", "info", "test");

    private final ArgusPlugin plugin;
    private final SsService ssService;

    public ArgusCommand(ArgusPlugin plugin) {
        this.plugin = plugin;
        this.ssService = new SsService(plugin);
    }

    @Override
    public boolean onCommand(CommandSender sender, Command command, String label, String[] args) {
        Messages msg = plugin.getMessages();

        if (args.length == 0) {
            sendHelp(sender);
            return true;
        }

        String sub = args[0].toLowerCase();

        if (SS_ALIASES.contains(sub)) {
            return handleCheck(sender, args);
        }

        if (!sender.hasPermission("argus.admin")) {
            msg.sendPrefixed(sender, "no_permission", null);
            return true;
        }
        switch (sub) {
            case "reload": handleReload(sender); break;
            case "info":   handleInfo(sender);   break;
            case "test":   handleTest(sender);   break;
            case "help":   sendHelp(sender);     break;
            default:
                sender.sendMessage(msg.prefix() + Messages.color("&cSubcomando desconocido: &f" + sub));
                sendHelp(sender);
                break;
        }
        return true;
    }

    private void sendHelp(CommandSender sender) {
        Messages msg = plugin.getMessages();
        sender.sendMessage(msg.prefix() + Messages.color("&7Subcomandos disponibles:"));
        if (sender.hasPermission("argus.ss.use") || sender instanceof ConsoleCommandSender) {
            sender.sendMessage(Messages.color("  &e/argus check <jugador> [razon] &7- emite token de Screen Share"));
        }
        if (sender.hasPermission("argus.admin")) {
            sender.sendMessage(Messages.color("  &e/argus reload &7- recarga config.yml"));
            sender.sendMessage(Messages.color("  &e/argus info &7- muestra estado y quota"));
            sender.sendMessage(Messages.color("  &e/argus test &7- health check de la API"));
        }
    }

    /**
     * /argus check &lt;player&gt; [razon...]
     * Reemplaza al viejo /ss top-level. Mismo comportamiento.
     */
    private boolean handleCheck(CommandSender sender, String[] args) {
        Messages msg = plugin.getMessages();

        if (args.length < 2) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/argus check <jugador> [razon]"));
            return true;
        }

        String targetName = args[1];
        String reason = "";
        if (args.length > 2) {
            StringBuilder sb = new StringBuilder();
            for (int i = 2; i < args.length; i++) {
                if (i > 2) sb.append(' ');
                sb.append(args[i]);
            }
            reason = sb.toString().trim();
        }

        SsService.Source src = sender instanceof ConsoleCommandSender
            ? SsService.Source.CONSOLE
            : SsService.Source.STAFF_MANUAL;
        ssService.issueScreenShare(sender, targetName, reason, src);
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
            String partial = args[0].toLowerCase();
            List<String> out = new ArrayList<>();
            // Sugerir SS aliases si tiene permiso
            if (sender.hasPermission("argus.ss.use")) {
                for (String s : SS_ALIASES) {
                    if (s.startsWith(partial)) out.add(s);
                }
            }
            // Sugerir admin subs si tiene permiso
            if (sender.hasPermission("argus.admin")) {
                for (String s : ADMIN_SUBS) {
                    if (s.startsWith(partial)) out.add(s);
                }
            }
            return out;
        }
        // /argus check <player>
        if (args.length == 2 && SS_ALIASES.contains(args[0].toLowerCase())
            && sender.hasPermission("argus.ss.use")) {
            String partial = args[1].toLowerCase();
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
