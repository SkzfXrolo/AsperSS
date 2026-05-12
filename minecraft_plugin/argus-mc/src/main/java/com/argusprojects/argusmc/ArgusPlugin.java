package com.argusprojects.argusmc;

import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.AnticheatListener;
import com.argusprojects.argusmc.anticheat.ViolationManager;
import com.argusprojects.argusmc.anticheat.packet.PacketEventsBootstrap;
import com.argusprojects.argusmc.api.ArgusApiClient;
import com.argusprojects.argusmc.commands.ArgusCommand;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.command.PluginCommand;
import org.bukkit.event.HandlerList;
import org.bukkit.plugin.java.JavaPlugin;

import java.util.logging.Level;

/**
 * Argus MC — main plugin class.
 *
 * <p>Hookea LuckyPerms automaticamente via Bukkit#hasPermission(...) — el plugin
 * no necesita codigo especifico para LP, basta con que el permiso este definido
 * en plugin.yml y LP responda a la consulta.
 *
 * <p>Componentes que vive aca y son inyectados a comandos/listeners:
 * <ul>
 *   <li>{@link ArgusConfig}      — wrapper sobre api.* y ss.*</li>
 *   <li>{@link AnticheatConfig}  — wrapper sobre anticheat.*</li>
 *   <li>{@link ArgusApiClient}   — cliente HTTP async</li>
 *   <li>{@link Messages}         — i18n / placeholders</li>
 *   <li>{@link ViolationManager} — cerebro del anti-cheat</li>
 *   <li>{@link AnticheatListener}— bundle de checks via eventos Bukkit</li>
 * </ul>
 */
public final class ArgusPlugin extends JavaPlugin {

    private ArgusConfig      argusConfig;
    private AnticheatConfig  anticheatConfig;
    private ArgusApiClient   apiClient;
    private Messages         messages;
    private ViolationManager violationManager;
    private AnticheatListener anticheatListener;
    private PacketEventsBootstrap packetEventsBootstrap;

    @Override
    public void onEnable() {
        saveDefaultConfig();
        reloadConfigState();

        registerCommand("argus", new ArgusCommand(this));

        // Anti-cheat
        this.violationManager = new ViolationManager(this);
        if (anticheatConfig.isEnabled()) {
            this.anticheatListener = new AnticheatListener(this, violationManager);
            getServer().getPluginManager().registerEvents(this.anticheatListener, this);
            getLogger().info("Anti-cheat ACTIVO (enforcement=" + anticheatConfig.isEnforcement() + ")");

            // Pack 47 — packet-based checks via PacketEvents (soft-dep).
            // Si el plugin PacketEvents no esta instalado, este boot es no-op:
            // el anti-cheat sigue funcionando con AnticheatListener Bukkit-based.
            try {
                this.packetEventsBootstrap = new PacketEventsBootstrap(this);
                if (packetEventsBootstrap.detect()) {
                    // Init en runTaskLater(1) — PacketEvents puede inicializar despues de nosotros.
                    getServer().getScheduler().runTaskLater(this, () -> packetEventsBootstrap.init(), 20L);
                }
            } catch (Throwable t) {
                getLogger().warning("PacketEventsBootstrap fallo (fallback Bukkit AC activo): " + t.getMessage());
            }
        } else {
            getLogger().info("Anti-cheat DESACTIVADO via config (anticheat.enabled=false).");
        }

        boolean lpPresent = getServer().getPluginManager().getPlugin("LuckyPerms") != null;
        getLogger().info("LuckyPerms detectado: " + (lpPresent ? "si (los permisos respetan tus grupos LP)" : "no (se usaran permisos OP por defecto)"));

        if (argusConfig.isMisconfigured()) {
            getLogger().log(Level.WARNING,
                "Argus no esta configurado todavia. Edita plugins/ArgusMC/config.yml y ejecuta /argus reload.");
        } else {
            apiClient.healthCheckAsync().thenAccept(result -> {
                if (result.success && result.authenticated) {
                    getLogger().info("Argus listo. Empresa: " + result.companyId
                        + " | quota: " + result.usedToday + "/" + result.dailyQuota);
                } else if (result.success) {
                    getLogger().warning("Conexion OK pero la API key no es valida. Revisa config.yml.");
                } else {
                    getLogger().warning("No se pudo conectar a Argus: " + result.errorMessage);
                }
            });
        }

        // Pack 46 — proactive alerts cada 5 min (asincrono, no bloquea tick)
        // El backend resume jugadores que estan escalando y devuelve mensajes
        // pre-formateados para whisper al staff con permiso 'argus.alerts'.
        getServer().getScheduler().runTaskTimerAsynchronously(this, () -> {
            try {
                if (argusConfig.isMisconfigured()) return;
                apiClient.getProactiveSuggestionsAsync().thenAccept(suggestions -> {
                    if (suggestions == null || suggestions.isEmpty()) return;
                    // Volver al thread principal para tocar jugadores
                    getServer().getScheduler().runTask(this, () -> {
                        for (org.bukkit.entity.Player p : getServer().getOnlinePlayers()) {
                            if (!p.hasPermission("argus.alerts")) continue;
                            for (String msg : suggestions) {
                                if (msg == null || msg.isEmpty()) continue;
                                p.sendMessage(
                                    com.argusprojects.argusmc.util.Messages.color(
                                        "&8[&b&lArgus AI&8] &7" + msg));
                            }
                        }
                    });
                });
            } catch (Exception ex) {
                getLogger().fine("proactive-alerts loop error: " + ex.getMessage());
            }
        }, 20L * 60 * 2,   // delay inicial: 2min para no spamear en restart
           20L * 60 * 5);  // periodo: cada 5min
    }

    @Override
    public void onDisable() {
        if (packetEventsBootstrap != null) {
            try { packetEventsBootstrap.shutdown(); } catch (Throwable ignored) {}
        }
        if (apiClient != null) {
            apiClient.shutdown();
        }
        // Desregistrar listeners para evitar leaks en /reload
        HandlerList.unregisterAll(this);
    }

    public void reloadConfigState() {
        reloadConfig();
        this.argusConfig     = new ArgusConfig(getConfig());
        this.anticheatConfig = new AnticheatConfig(getConfig());
        this.messages        = new Messages(getConfig());
        if (this.apiClient != null) {
            this.apiClient.shutdown();
        }
        this.apiClient = new ArgusApiClient(this, argusConfig);
    }

    public ArgusConfig getArgusConfig()           { return argusConfig; }
    public AnticheatConfig getAnticheatConfig()   { return anticheatConfig; }
    public ArgusApiClient getApiClient()          { return apiClient; }
    public Messages getMessages()                 { return messages; }
    public ViolationManager getViolationManager() { return violationManager; }
    public PacketEventsBootstrap getPacketEventsBootstrap() { return packetEventsBootstrap; }

    private void registerCommand(String name, org.bukkit.command.CommandExecutor exec) {
        PluginCommand cmd = getCommand(name);
        if (cmd == null) {
            getLogger().severe("Comando '" + name + "' no esta registrado en plugin.yml");
            return;
        }
        cmd.setExecutor(exec);
        if (exec instanceof org.bukkit.command.TabCompleter tc) {
            cmd.setTabCompleter(tc);
        }
    }
}
