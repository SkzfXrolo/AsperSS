package com.argusprojects.argusmc.anticheat.packet;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.checks.AimSnapPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AutoTotemCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BlockReachCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BoatFlyAdvancedCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BoatFlyCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BowAimCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.CPSPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.CritCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.FastBreakCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.FastPlaceCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.InvMovePacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.InvalidRotationCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.JetpackCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.KillauraAimCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.KillauraBlockingCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.KillauraSwingPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.MultiVelocityCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.NukerCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.ProjectileAimCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.PhaseCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.PingSpoofCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.ReachPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.SpeedPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.SpiderCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.StepCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.TimerCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.VClipCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.VelocityCheck;
import com.github.retrooper.packetevents.event.PacketListenerPriority;
import com.github.retrooper.packetevents.event.SimplePacketListenerAbstract;
import com.github.retrooper.packetevents.event.simple.PacketPlayReceiveEvent;
import com.github.retrooper.packetevents.event.simple.PacketPlaySendEvent;
import com.github.retrooper.packetevents.protocol.packettype.PacketType;
import com.github.retrooper.packetevents.protocol.player.DiggingAction;
import com.github.retrooper.packetevents.wrapper.play.client.WrapperPlayClientInteractEntity;
import com.github.retrooper.packetevents.wrapper.play.client.WrapperPlayClientPlayerDigging;
import com.github.retrooper.packetevents.wrapper.play.client.WrapperPlayClientPlayerFlying;
import org.bukkit.Bukkit;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;

import java.lang.ref.WeakReference;
import java.util.HashMap;
import java.util.Map;
import java.util.UUID;

/**
 * Pack 47 — Listener principal de packets (PacketEvents 2.x).
 *
 * <p>Recibe packets crudos del cliente y server, mantiene actualizado el
 * {@link PacketDataStore}, y ejecuta cada uno de los 10 checks packet-based
 * en cada packet relevante. Si un check produce una {@link Violation}, la
 * pasa al {@link com.argusprojects.argusmc.anticheat.ViolationManager}
 * existente (mismo flujo que los checks Bukkit-based).
 *
 * <p>IMPORTANTE: los handlers corren en el thread de Netty. NO tocar
 * APIs de Bukkit que requieran main thread aca; cualquier accion de
 * consecuencia (kick/ban) la hace ViolationManager con runTask al main.
 */
public final class PacketAnticheatListener extends SimplePacketListenerAbstract {

    private final ArgusPlugin plugin;
    private final PacketDataStore store;

    private final TimerCheck                timerCheck;
    private final PhaseCheck                phaseCheck;
    private final VelocityCheck             velocityCheck;
    private final InvalidRotationCheck      invalidRotationCheck;
    private final ReachPacketCheck          reachCheck;
    private final KillauraSwingPacketCheck  swingCheck;
    private final AimSnapPacketCheck        aimSnapCheck;
    private final PingSpoofCheck            pingSpoofCheck;
    private final CPSPacketCheck            cpsCheck;
    private final InvMovePacketCheck        invMoveCheck;
    private final VClipCheck                vclipCheck;
    private final StepCheck                 stepCheck;
    private final SpeedPacketCheck          speedPacketCheck;
    private final FastPlaceCheck            fastPlaceCheck;
    private final FastBreakCheck            fastBreakCheck;
    private final NukerCheck                nukerCheck;
    private final AutoTotemCheck            autoTotemCheck;
    private final KillauraAimCheck          killauraAimCheck;
    private final KillauraBlockingCheck     killauraBlockingCheck;
    private final BoatFlyCheck              boatFlyCheck;
    private final JetpackCheck              jetpackCheck;
    private final SpiderCheck               spiderCheck;
    private final MultiVelocityCheck        multiVelocityCheck;
    private final BlockReachCheck           blockReachCheck;
    private final CritCheck                 critCheck;
    private final ProjectileAimCheck        projectileAimCheck;
    private final BowAimCheck               bowAimCheck;
    private final BoatFlyAdvancedCheck      boatFlyAdvancedCheck;

    /**
     * #512 — Cache entityId -> Entity para evitar el linear scan de
     * world.getEntities() en cada InteractEntity packet.
     * Capacity-bounded: limpiamos mas viejas que el TTL al hacer lookup miss.
     */
    private final Map<Integer, CachedEntity> entityCache = new HashMap<>();
    private static final long ENTITY_CACHE_TTL_MS = 2_000L;
    private static final int  ENTITY_CACHE_MAX    = 256;

    private static final class CachedEntity {
        final WeakReference<Entity> ref;
        final long resolvedAtMs;
        CachedEntity(Entity e) { this.ref = new WeakReference<>(e); this.resolvedAtMs = System.currentTimeMillis(); }
    }

    public PacketAnticheatListener(ArgusPlugin plugin, PacketDataStore store) {
        super(PacketListenerPriority.NORMAL);
        this.plugin = plugin;
        this.store  = store;

        this.timerCheck           = new TimerCheck(plugin);
        this.phaseCheck           = new PhaseCheck(plugin);
        this.velocityCheck        = new VelocityCheck(plugin);
        this.invalidRotationCheck = new InvalidRotationCheck(plugin);
        this.reachCheck           = new ReachPacketCheck(plugin);
        this.swingCheck           = new KillauraSwingPacketCheck(plugin);
        this.aimSnapCheck         = new AimSnapPacketCheck(plugin);
        this.pingSpoofCheck       = new PingSpoofCheck(plugin);
        this.cpsCheck             = new CPSPacketCheck(plugin);
        this.invMoveCheck         = new InvMovePacketCheck(plugin);
        this.vclipCheck           = new VClipCheck(plugin);
        this.stepCheck            = new StepCheck(plugin);
        this.speedPacketCheck     = new SpeedPacketCheck(plugin);
        this.fastPlaceCheck       = new FastPlaceCheck(plugin);
        this.fastBreakCheck       = new FastBreakCheck(plugin);
        this.nukerCheck           = new NukerCheck(plugin);
        this.autoTotemCheck       = new AutoTotemCheck(plugin);
        this.killauraAimCheck     = new KillauraAimCheck(plugin);
        this.killauraBlockingCheck= new KillauraBlockingCheck(plugin);
        this.boatFlyCheck         = new BoatFlyCheck(plugin);
        this.jetpackCheck         = new JetpackCheck(plugin);
        this.spiderCheck          = new SpiderCheck(plugin);
        this.multiVelocityCheck   = new MultiVelocityCheck(plugin);
        this.blockReachCheck      = new BlockReachCheck(plugin);
        this.critCheck            = new CritCheck(plugin);
        this.projectileAimCheck   = new ProjectileAimCheck(plugin);
        this.bowAimCheck          = new BowAimCheck(plugin);
        this.boatFlyAdvancedCheck = new BoatFlyAdvancedCheck(plugin);
    }

    public CritCheck getCritCheck() { return critCheck; }
    public ProjectileAimCheck getProjectileAimCheck() { return projectileAimCheck; }
    public BowAimCheck getBowAimCheck() { return bowAimCheck; }

    /** Acceso al sink para checks que disparan desde el bridge Bukkit. */
    public ViolationSink getSink() { return sink(); }
    public AutoTotemCheck getAutoTotemCheck() { return autoTotemCheck; }

    // ──────────────────────────────────────────────────────────────────────
    //  Packets recibidos del CLIENTE
    // ──────────────────────────────────────────────────────────────────────
    @Override
    public void onPacketPlayReceive(PacketPlayReceiveEvent event) {
        try {
            // #511: short-circuit global. Si el AC esta off (config) no tocamos
            // nada de packets — ahorra MUCHO CPU en servers grandes (cada
            // packet de movimiento es ~20 invocaciones/segundo/jugador).
            var ac = plugin.getAnticheatConfig();
            if (ac == null || !ac.isEnabled()) return;

            UUID uuid = event.getUser() != null ? event.getUser().getUUID() : null;
            if (uuid == null) return;

            Player player = Bukkit.getPlayer(uuid);
            if (player == null) return;
            if (player.hasPermission("argus.ac.bypass")) return;

            PacketDataStore.State s = store.get(uuid);

            var type = event.getPacketType();

            if (type == PacketType.Play.Client.PLAYER_POSITION
                || type == PacketType.Play.Client.PLAYER_POSITION_AND_ROTATION
                || type == PacketType.Play.Client.PLAYER_ROTATION
                || type == PacketType.Play.Client.PLAYER_FLYING) {

                long now = System.currentTimeMillis();

                // PlayerFlying es un packet "no movement" (solo onGround flag),
                // pero los demas tambien llevan onGround. Lo usamos para checks
                // que dependen de "venir del suelo".
                WrapperPlayClientPlayerFlying wrap = new WrapperPlayClientPlayerFlying(event);
                boolean nowOnGround;
                try {
                    nowOnGround = wrap.isOnGround();
                } catch (Throwable t) {
                    nowOnGround = s.lastOnGround;
                }

                if (type != PacketType.Play.Client.PLAYER_FLYING) {
                    if (wrap.hasPositionChanged()) {
                        double nx = wrap.getLocation().getX();
                        double ny = wrap.getLocation().getY();
                        double nz = wrap.getLocation().getZ();
                        // Timer (tick rate) check ANTES de actualizar last position
                        s.pushMove(now);
                        timerCheck.handlePositionPacket(player, s, now, sink());
                        // Phase / NoClip — verifica que el delta no atraviese paredes.
                        phaseCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        // Velocity check — el cliente debe respetar la velocity asignada.
                        velocityCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        // VClip — delta Y impossible en un packet (Pack 48 #482).
                        vclipCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        // Step — subir bloque sin curva de salto (Pack 48 #483).
                        stepCheck.handlePositionPacket(player, s, nx, ny, nz, nowOnGround, sink());
                        // Speed real horizontal (Pack 48 #484).
                        speedPacketCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());
                        // Round 2: BoatFly / Jetpack / Spider / MultiVelocity / BoatFlyAdv.
                        boatFlyCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());
                        jetpackCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());
                        spiderCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        multiVelocityCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        boatFlyAdvancedCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());

                        s.lastDeltaY = ny - s.lastY;
                        s.lastX = nx;
                        s.lastY = ny;
                        s.lastZ = nz;
                        s.lastMoveMs = now;
                    }
                    if (wrap.hasRotationChanged()) {
                        float ny  = wrap.getLocation().getYaw();
                        float npi = wrap.getLocation().getPitch();
                        // Invalid pitch: |pitch| > 90 es imposible para cliente vanilla.
                        invalidRotationCheck.handleRotation(player, s, ny, npi, sink());
                        // Aim snap: delta yaw entre packets vs delta esperado.
                        aimSnapCheck.handleRotation(player, s, ny, npi, sink());
                        // Round 2: buffer de rotaciones para KillauraAim / BowAim.
                        s.pushRotation(ny, npi, now);
                        s.lastYaw   = ny;
                        s.lastPitch = npi;
                    }
                }

                // Tracking de onGround para checks de step/fly/jump.
                if (nowOnGround) {
                    s.lastOnGroundMs = now;
                }
                s.lastOnGround = nowOnGround;

            } else if (type == PacketType.Play.Client.INTERACT_ENTITY) {
                WrapperPlayClientInteractEntity wrap = new WrapperPlayClientInteractEntity(event);
                if (wrap.getAction() == WrapperPlayClientInteractEntity.InteractAction.ATTACK) {
                    long now = System.currentTimeMillis();
                    s.lastAttackMs = now;
                    s.pushAttack(now);
                    // Resolver entidad por id
                    Entity target = resolveEntity(player.getWorld(), wrap.getEntityId());
                    // Reach packet-based (posicion EXACTA en el tick del hit).
                    if (target != null) {
                        reachCheck.handleAttack(player, target, s, sink());
                        swingCheck.handleAttack(player, target, s, now, sink());
                        // Round 2: KillauraAim / KillauraBlocking.
                        killauraAimCheck.handleAttack(player, target, s, now, sink());
                        killauraBlockingCheck.handleAttack(player, target, s, now, sink());
                    }
                    // CPS verdadero a nivel packet.
                    cpsCheck.handleAttack(player, s, now, sink());
                }

            } else if (type == PacketType.Play.Client.ANIMATION) {
                long now = System.currentTimeMillis();
                s.lastSwingMs = now;
                s.pushSwing(now);
                swingCheck.handleSwing(player, s, now, sink());

            } else if (type == PacketType.Play.Client.KEEP_ALIVE) {
                long now = System.currentTimeMillis();
                if (s.lastKeepAliveSentMs > 0) {
                    long rtt = now - s.lastKeepAliveSentMs;
                    s.pingMs = rtt;
                    pingSpoofCheck.handleKeepAliveResponse(player, s, rtt, sink());
                }
                s.lastKeepAliveRecvMs = now;

            } else if (type == PacketType.Play.Client.CLICK_WINDOW) {
                long now = System.currentTimeMillis();
                s.lastClickWindowMs = now;
                invMoveCheck.handleClickWindow(player, s, now, sink());

            } else if (type == PacketType.Play.Client.PLAYER_BLOCK_PLACEMENT) {
                long now = System.currentTimeMillis();
                fastPlaceCheck.handleBlockPlacement(player, s, now, sink());
                // BlockReach (round 2) — distancia ojos→bloque target.
                try {
                    var wrapP = new com.github.retrooper.packetevents.wrapper.play.client
                        .WrapperPlayClientPlayerBlockPlacement(event);
                    var pos = wrapP.getBlockPosition();
                    if (pos != null) {
                        blockReachCheck.handleBlockInteract(player, s, pos.getX(), pos.getY(), pos.getZ(), sink());
                    }
                } catch (Throwable ignored) {}

            } else if (type == PacketType.Play.Client.PLAYER_DIGGING) {
                WrapperPlayClientPlayerDigging wrap = new WrapperPlayClientPlayerDigging(event);
                long now = System.currentTimeMillis();
                DiggingAction action = wrap.getAction();
                if (action == DiggingAction.START_DIGGING) {
                    org.bukkit.Material mat = resolveBlock(player, wrap);
                    fastBreakCheck.handleStartDigging(player, s, now, mat);
                    var pos = wrap.getBlockPosition();
                    if (pos != null) {
                        blockReachCheck.handleBlockInteract(player, s, pos.getX(), pos.getY(), pos.getZ(), sink());
                    }
                } else if (action == DiggingAction.FINISHED_DIGGING) {
                    org.bukkit.Material mat = resolveBlock(player, wrap);
                    fastBreakCheck.handleFinishDigging(player, s, now, mat, sink());
                    nukerCheck.handleFinishDigging(player, s, now, mat, sink());
                } else if (action == DiggingAction.CANCELLED_DIGGING) {
                    s.currentBreakStartMs = 0L;
                    s.currentBreakBlockMaterial = null;
                }
            }
        } catch (Throwable t) {
            // #514: defensivo + lazy log (no construye string si fine() esta off).
            plugin.getLogger().fine(() -> "[Argus/Packet] receive err: "
                + t.getClass().getSimpleName() + " " + t.getMessage());
        }
    }

    // ──────────────────────────────────────────────────────────────────────
    //  Packets enviados desde el SERVIDOR
    // ──────────────────────────────────────────────────────────────────────
    @Override
    public void onPacketPlaySend(PacketPlaySendEvent event) {
        try {
            UUID uuid = event.getUser() != null ? event.getUser().getUUID() : null;
            if (uuid == null) return;
            PacketDataStore.State s = store.peek(uuid);
            if (s == null) return;

            var type = event.getPacketType();
            if (type == PacketType.Play.Server.KEEP_ALIVE) {
                s.lastKeepAliveSentMs = System.currentTimeMillis();
            }
        } catch (Throwable ignored) {
        }
    }

    private Entity resolveEntity(org.bukkit.World w, int entityId) {
        if (w == null) return null;
        long now = System.currentTimeMillis();
        synchronized (entityCache) {
            CachedEntity cached = entityCache.get(entityId);
            if (cached != null) {
                Entity hit = cached.ref.get();
                if (hit != null && hit.isValid() && (now - cached.resolvedAtMs) < ENTITY_CACHE_TTL_MS) {
                    return hit;
                }
                entityCache.remove(entityId);
            }
            // Cap: limpia viejas si excede.
            if (entityCache.size() > ENTITY_CACHE_MAX) {
                entityCache.entrySet().removeIf(e -> (now - e.getValue().resolvedAtMs) > ENTITY_CACHE_TTL_MS);
                if (entityCache.size() > ENTITY_CACHE_MAX) {
                    entityCache.clear(); // last resort
                }
            }
        }
        // Cache miss: scan + cache hit
        for (Entity ent : w.getEntities()) {
            if (ent.getEntityId() == entityId) {
                synchronized (entityCache) {
                    entityCache.put(entityId, new CachedEntity(ent));
                }
                return ent;
            }
        }
        return null;
    }

    /** Devuelve el Material del bloque target del PlayerDigging packet (best-effort). */
    private org.bukkit.Material resolveBlock(Player player, WrapperPlayClientPlayerDigging wrap) {
        try {
            var pos = wrap.getBlockPosition();
            if (pos == null) return null;
            org.bukkit.World w = player.getWorld();
            return w.getBlockAt(pos.getX(), pos.getY(), pos.getZ()).getType();
        } catch (Throwable t) {
            return null;
        }
    }

    /** Sink centralizado: cualquier check llama a sink().flag(v) para reportar. */
    private ViolationSink sink() {
        return v -> {
            if (v == null) return;
            // Bukkit operations deben volver al main thread.
            Bukkit.getScheduler().runTask(plugin, () ->
                plugin.getViolationManager().flag(v));
        };
    }

    @FunctionalInterface
    public interface ViolationSink {
        void flag(Violation v);
        default Violation make(Player p, String name, ViolationLevel lvl, String details) {
            Violation v = new Violation(p, name, lvl, details);
            this.flag(v);
            return v;
        }
    }
}
