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
    private static final List<String> ADMIN_SUBS   = Arrays.asList("reload", "info", "test", "debug", "violations", "duda", "pregunta", "ask", "admin");
    /** Sub-subcomandos bajo /argus admin (Pack 48 bloque 4). */
    private static final List<String> ADMIN_NESTED = Arrays.asList("reload", "debug", "testpacket", "clearviolations");

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
            case "reload":     handleReload(sender);     break;
            case "info":       handleInfo(sender);       break;
            case "test":       handleTest(sender);       break;
            case "debug":      handleDebug(sender);      break;
            case "violations": handleViolations(sender, args); break;
            case "duda":       handleDuda(sender, args); break;
            case "pregunta":
            case "ask":        handlePregunta(sender, args); break;
            case "admin":      handleAdmin(sender, args); break;
            case "help":       sendHelp(sender);         break;
            default:
                sender.sendMessage(msg.prefix() + Messages.color("&cSubcomando desconocido: &f" + sub));
                sendHelp(sender);
                break;
        }
        return true;
    }

    /**
     * /argus admin &lt;sub&gt; — namespace para operaciones administrativas.
     *
     * <p>Sub-subcomandos (Pack 48 bloque 4):
     * <ul>
     *   <li><b>reload</b> — recarga config.yml (alias de /argus reload). (#501)</li>
     *   <li><b>debug [jugador]</b> — toggle debug global o telemetria de un
     *       jugador especifico desde el packet datastore. (#502)</li>
     *   <li><b>testpacket &lt;jugador&gt;</b> — inyecta una violation sintetica
     *       a nivel packet para verificar el pipeline (sink, ViolationManager,
     *       AI Oracle, Discord, etc.). (#503)</li>
     *   <li><b>clearviolations [jugador]</b> — limpia el acumulador de la
     *       sliding window y los buffers del packet datastore. (#506)</li>
     * </ul>
     */
    private void handleAdmin(CommandSender sender, String[] args) {
        Messages msg = plugin.getMessages();
        if (args.length < 2) {
            sendAdminHelp(sender);
            return;
        }
        String sub = args[1].toLowerCase();
        switch (sub) {
            case "reload":           handleAdminReload(sender);          break;
            case "debug":            handleAdminDebug(sender, args);     break;
            case "testpacket":       handleAdminTestPacket(sender, args); break;
            case "help":             sendAdminHelp(sender);              break;
            default:
                sender.sendMessage(msg.prefix() + Messages.color("&cSub-comando admin desconocido: &f" + sub));
                sendAdminHelp(sender);
                break;
        }
    }

    private void sendAdminHelp(CommandSender sender) {
        sender.sendMessage(Messages.color("&7Subcomandos &e/argus admin&7:"));
        sender.sendMessage(Messages.color("  &e/argus admin reload &7- recarga config.yml"));
        sender.sendMessage(Messages.color("  &e/argus admin debug [jugador] &7- debug global o telemetria de jugador"));
        sender.sendMessage(Messages.color("  &e/argus admin testpacket <jugador> &7- emite test packet violation"));
        sender.sendMessage(Messages.color("  &e/argus admin clearviolations [jugador] &7- limpia violations"));
    }

    /** #501 — /argus admin reload */
    private void handleAdminReload(CommandSender sender) {
        handleReload(sender);
    }

    /**
     * #502 — /argus admin debug [jugador].
     *
     * <p>Sin argumento: toggle del modo debug global (igual que /argus debug).
     * Con jugador: dump de telemetria packet-based del PacketDataStore para
     * ese jugador (ping, ultimas posiciones, contadores, timestamps).
     */
    private void handleAdminDebug(CommandSender sender, String[] args) {
        Messages msg = plugin.getMessages();
        if (args.length < 3) {
            handleDebug(sender);
            return;
        }
        String targetName = args[2];
        Player target = Bukkit.getPlayerExact(targetName);
        if (target == null) {
            msg.sendPrefixed(sender, "player_not_found", Messages.ph("player", targetName));
            return;
        }
        var bootstrap = plugin.getPacketEventsBootstrap();
        if (bootstrap == null || !bootstrap.isInitialized() || bootstrap.getDataStore() == null) {
            sender.sendMessage(msg.prefix() + Messages.color(
                "&7Packet anti-cheat NO inicializado (instala PacketEvents)."));
            return;
        }
        var state = bootstrap.getDataStore().peek(target.getUniqueId());
        if (state == null) {
            sender.sendMessage(msg.prefix() + Messages.color(
                "&7No hay estado packet para &e" + target.getName() + "&7. Pidele que se mueva una vez."));
            return;
        }
        long now = System.currentTimeMillis();
        sender.sendMessage(Messages.color("&7&m─────────────────────────────────────────"));
        sender.sendMessage(Messages.color("&8[&b&lArgus AC Debug&8] &f" + target.getName()));
        sender.sendMessage(Messages.color(String.format(
            "&7pos: &fX=%.2f Y=%.2f Z=%.2f &7yaw=&f%.1f &7pitch=&f%.1f",
            state.lastX, state.lastY, state.lastZ, state.lastYaw, state.lastPitch)));
        sender.sendMessage(Messages.color(String.format(
            "&7ping: &f%dms &7onGround: &f%s &7lastDy: &f%.3f",
            state.pingMs, String.valueOf(state.lastOnGround), state.lastDeltaY)));
        sender.sendMessage(Messages.color(String.format(
            "&7cps(1s): &f%d &7swing-age: &f%dms &7attack-age: &f%dms",
            state.recentAttacksWithin(1_000L, now),
            state.lastSwingMs > 0 ? (now - state.lastSwingMs) : -1L,
            state.lastAttackMs > 0 ? (now - state.lastAttackMs) : -1L)));
        sender.sendMessage(Messages.color(String.format(
            "&7places(1s): &f%d &7breaks(1s): &f%d &7speed-overflow: &f%d",
            state.recentPlacesWithin(1_000L, now),
            state.recentBreaksWithin(1_000L, now),
            state.speedOverflowCounter)));
        sender.sendMessage(Messages.color(String.format(
            "&7teleporting: &f%s &7inv-open: &f%s &7damage-age: &f%dms",
            String.valueOf(state.teleporting),
            String.valueOf(state.inventoryOpen),
            state.lastDamageTakenMs > 0 ? (now - state.lastDamageTakenMs) : -1L)));
        int vios = plugin.getViolationManager().countRecent(target.getUniqueId());
        sender.sendMessage(Messages.color("&7violations en window: &e" + vios));
        sender.sendMessage(Messages.color("&7&m─────────────────────────────────────────"));
    }

    /**
     * #503 — /argus admin testpacket &lt;jugador&gt; [level].
     *
     * <p>Emite una violation sintetica (check name "admin_testpacket") al
     * ViolationManager para verificar end-to-end: sliding window, broadcast
     * staff, kick (si supera threshold), backend report, Discord webhook,
     * AI Oracle. NO ejecuta accion enforced (level por defecto LOW solo
     * dispara alerta a staff).
     */
    private void handleAdminTestPacket(CommandSender sender, String[] args) {
        Messages msg = plugin.getMessages();
        if (args.length < 3) {
            sender.sendMessage(msg.prefix() + Messages.color(
                "&7Uso: &f/argus admin testpacket <jugador> [level]"));
            sender.sendMessage(Messages.color("&7Levels: LOW MID HIGH CRITICAL (default LOW)"));
            return;
        }
        Player target = Bukkit.getPlayerExact(args[2]);
        if (target == null) {
            msg.sendPrefixed(sender, "player_not_found", Messages.ph("player", args[2]));
            return;
        }
        com.argusprojects.argusmc.anticheat.ViolationLevel level =
            com.argusprojects.argusmc.anticheat.ViolationLevel.LOW;
        if (args.length >= 4) {
            try {
                level = com.argusprojects.argusmc.anticheat.ViolationLevel.valueOf(args[3].toUpperCase());
            } catch (IllegalArgumentException ex) {
                sender.sendMessage(msg.prefix() + Messages.color(
                    "&cLevel desconocido: &f" + args[3] + "&c. Usa LOW/MID/HIGH/CRITICAL."));
                return;
            }
        }
        com.argusprojects.argusmc.anticheat.Violation v =
            new com.argusprojects.argusmc.anticheat.Violation(
                target, "admin_testpacket", level,
                "/argus admin testpacket invocado por " + sender.getName());
        plugin.getViolationManager().flag(v);
        sender.sendMessage(msg.prefix() + Messages.color(
            "&aTest packet violation emitida &7para &e" + target.getName()
                + " &7nivel &b" + level.name() + "&7. Mira el chat del staff y los logs."));
    }

    /**
     * /argus debug — toggle modo debug del anticheat. Cuando esta ON, cada hit
     * loguea la telemetria completa (distancia, angulo, CPS, swing-age, yaw)
     * a todos los staff con permiso 'argus.alerts'. Util para entender por
     * que un cheat no esta siendo flageado.
     */
    private void handleDebug(CommandSender sender) {
        com.argusprojects.argusmc.anticheat.AnticheatListener.debugMode =
            !com.argusprojects.argusmc.anticheat.AnticheatListener.debugMode;
        boolean now = com.argusprojects.argusmc.anticheat.AnticheatListener.debugMode;
        Messages msg = plugin.getMessages();
        sender.sendMessage(msg.prefix() + Messages.color(
            now ? "&aAnticheat DEBUG MODE: ON &7- ahora cada hit logea metricas en chat para staff."
                : "&7Anticheat DEBUG MODE: OFF"));
    }

    /**
     * /argus duda &lt;jugador&gt; — pide al Argus AI Oracle que evalue al
     * jugador con TODA su evidencia disponible y devuelve un veredicto
     * humanizado (estilo staff senior) en chat al staff que lo invoco.
     *
     * <p>Esto es la version "on demand" del Oracle. La version automatica
     * se dispara con cada Violation desde {@link com.argusprojects.argusmc.anticheat.ViolationManager}.
     */
    private void handleDuda(CommandSender sender, String[] args) {
        Messages msg = plugin.getMessages();
        if (args.length < 2) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/argus duda <jugador>"));
            return;
        }
        Player target = org.bukkit.Bukkit.getPlayerExact(args[1]);
        if (target == null) {
            msg.sendPrefixed(sender, "player_not_found", Messages.ph("player", args[1]));
            return;
        }
        sender.sendMessage(msg.prefix() + Messages.color(
            "&7Consultando al Argus AI sobre &e" + target.getName() + "&7..."));

        // Sintetizamos una "violation" placeholder solo para que el endpoint
        // construya la evidencia completa (real lookup en BD).
        com.argusprojects.argusmc.anticheat.Violation synth =
            new com.argusprojects.argusmc.anticheat.Violation(
                target, "manual_query",
                com.argusprojects.argusmc.anticheat.ViolationLevel.LOW,
                "/argus duda invocado por " + sender.getName());

        plugin.getApiClient().evaluateAiAsync(synth, "none")
            .whenComplete((verdict, err) -> org.bukkit.Bukkit.getScheduler().runTask(plugin, () -> {
                if (err != null || verdict == null) {
                    sender.sendMessage(msg.prefix() + Messages.color(
                        "&cNo se pudo consultar al Oracle. Verifica conexion con la API."));
                    return;
                }
                String aiAction = verdict.mergedAction != null ? verdict.mergedAction : verdict.action;
                if (aiAction == null) aiAction = "none";
                sender.sendMessage(Messages.color("&7&m─────────────────────────────────────────"));
                sender.sendMessage(Messages.color(String.format(
                    "&8[&b&lArgus AI&8] &fVeredicto sobre &e%s",
                    target.getName())));
                sender.sendMessage(Messages.color(String.format(
                    "&7Score: &f%.2f &8| &7Confianza: &f%.2f &8| &7Accion: &b%s",
                    verdict.score, verdict.confidence, aiAction.toUpperCase())));
                if (verdict.topFactor != null && !verdict.topFactor.isEmpty()) {
                    sender.sendMessage(Messages.color("&7Factor principal: &f" + verdict.topFactor));
                }
                String reasoning = verdict.reasoning == null ? "(sin reasoning)" : verdict.reasoning;
                sender.sendMessage(Messages.color("&f" + reasoning));
                sender.sendMessage(Messages.color("&7&m─────────────────────────────────────────"));
            }));
    }

    /**
     * /argus pregunta &lt;texto libre&gt; — chat conversacional con el Oracle.
     *
     * <p>Ejemplos:
     * <ul>
     *   <li><code>/argus pregunta como esta Pinkraft</code></li>
     *   <li><code>/argus pregunta historial de Mateo</code></li>
     *   <li><code>/argus pregunta resumen del dia</code></li>
     *   <li><code>/argus pregunta top sospechosos</code></li>
     *   <li><code>/argus pregunta que hago con Juan</code></li>
     * </ul>
     *
     * <p>El Oracle responde en lenguaje humano basado en datos reales
     * de la BD (violations, scans, decisiones previas, modelo ML).
     */
    private void handlePregunta(CommandSender sender, String[] args) {
        Messages msg = plugin.getMessages();
        if (args.length < 2) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/argus pregunta <texto>"));
            sender.sendMessage(Messages.color("&7Ejemplos: 'como esta Pinkraft', 'resumen del dia', 'top sospechosos'"));
            return;
        }
        StringBuilder sb = new StringBuilder();
        for (int i = 1; i < args.length; i++) {
            if (i > 1) sb.append(' ');
            sb.append(args[i]);
        }
        String text = sb.toString().trim();
        if (text.isEmpty()) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/argus pregunta <texto>"));
            return;
        }
        sender.sendMessage(msg.prefix() + Messages.color("&7Consultando al Oracle..."));
        plugin.getApiClient().askAssistantAsync(text)
            .whenComplete((response, err) -> org.bukkit.Bukkit.getScheduler().runTask(plugin, () -> {
                if (err != null || response == null || !response.success) {
                    sender.sendMessage(msg.prefix() + Messages.color(
                        "&cNo se pudo consultar al Oracle. Verifica conexion."));
                    return;
                }
                sender.sendMessage(Messages.color("&7&m─────────────────────────────────────────"));
                sender.sendMessage(Messages.color("&8[&b&lArgus AI&8] &7Tu pregunta: &f" + text));
                String answer = response.answer != null ? response.answer : "(sin respuesta)";
                // Splitear en lineas para que se vea bien en chat
                for (String line : answer.split("\n")) {
                    if (line.trim().isEmpty()) continue;
                    sender.sendMessage(Messages.color("&f" + line));
                }
                sender.sendMessage(Messages.color("&7&m─────────────────────────────────────────"));
            }));
    }

    /**
     * /argus violations [jugador] — muestra cuantas violations recientes
     * tiene un jugador en la sliding window del manager.
     */
    private void handleViolations(CommandSender sender, String[] args) {
        Messages msg = plugin.getMessages();
        if (args.length < 2) {
            sender.sendMessage(msg.prefix() + Messages.color("&7Uso: &f/argus violations <jugador>"));
            return;
        }
        Player target = org.bukkit.Bukkit.getPlayerExact(args[1]);
        if (target == null) {
            msg.sendPrefixed(sender, "player_not_found", Messages.ph("player", args[1]));
            return;
        }
        int count = plugin.getViolationManager().countRecent(target.getUniqueId());
        sender.sendMessage(msg.prefix() + Messages.color(
            "&7" + target.getName() + " tiene &e" + count + " &7violations en la ventana actual."));
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
            sender.sendMessage(Messages.color("  &e/argus debug &7- toggle telemetria por hit"));
            sender.sendMessage(Messages.color("  &e/argus violations <jugador> &7- ver violations recientes"));
            sender.sendMessage(Messages.color("  &e/argus duda <jugador> &7- consulta al Argus AI Oracle"));
            sender.sendMessage(Messages.color("  &e/argus pregunta <texto> &7- chat con el Oracle (lenguaje natural)"));
            sender.sendMessage(Messages.color("  &e/argus admin &7- subcomandos admin (reload/debug/testpacket/clearviolations)"));
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
        // /argus admin <sub>  (Pack 48 #501-#506)
        if (args.length == 2 && "admin".equalsIgnoreCase(args[0])
            && sender.hasPermission("argus.admin")) {
            String partial = args[1].toLowerCase();
            List<String> out = new ArrayList<>();
            for (String s : ADMIN_NESTED) {
                if (s.startsWith(partial)) out.add(s);
            }
            return out;
        }
        // /argus admin <sub> <player>
        if (args.length == 3 && "admin".equalsIgnoreCase(args[0])
            && sender.hasPermission("argus.admin")) {
            String partial = args[2].toLowerCase();
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
