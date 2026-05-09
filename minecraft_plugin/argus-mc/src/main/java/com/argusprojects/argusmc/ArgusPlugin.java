package com.argusprojects.argusmc;

import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.AnticheatListener;
import com.argusprojects.argusmc.anticheat.ViolationManager;
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
    }

    @Override
    public void onDisable() {
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
