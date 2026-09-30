package com.argusprojects.argusmc.anticheat.packet;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.checks.AimSnapPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AimbotCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AntiKnockbackCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AutoArmorCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AutoClickerAdvancedCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AutoEatCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AutoPotionCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.FastBowCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.FastEatCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.KillauraNoSwingCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.KillauraRotationCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.KillauraThruWallCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.LiquidJesusCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.NoSlowDownCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.NoSlowSneakCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.PhaseClipCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.Reach3DCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.RegenCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.ScaffoldRotationCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.ScaffoldTowerCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.TimerJitterCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.TracersCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.NoFallPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.AutoTotemCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BackstabCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BlockGlitchCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BlockReachCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BoatFlyAdvancedCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BoatFlyCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.BowAimCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.CPSPacketCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.ChatMacroCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.CritCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.HitboxExpansionCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.InventoryTeleportCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.ItemPickupCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.LiquidWalkCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.MeleeFlyCheck;
import com.argusprojects.argusmc.anticheat.packet.checks.NamedItemSpamCheck;
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
    private final HitboxExpansionCheck      hitboxExpansionCheck;
    private final BackstabCheck             backstabCheck;
    private final MeleeFlyCheck             meleeFlyCheck;
    private final BlockGlitchCheck          blockGlitchCheck;
    private final ItemPickupCheck           itemPickupCheck;
    private final InventoryTeleportCheck    inventoryTeleportCheck;
    private final LiquidWalkCheck           liquidWalkCheck;
    private final ChatMacroCheck            chatMacroCheck;
    private final NamedItemSpamCheck        namedItemSpamCheck;
    private final AutoClickerAdvancedCheck  autoClickerAdvancedCheck;

    private final KillauraRotationCheck  killauraRotationCheck;
    private final KillauraNoSwingCheck   killauraNoSwingCheck;
    private final KillauraThruWallCheck  killauraThruWallCheck;
    private final ScaffoldRotationCheck  scaffoldRotationCheck;
    private final ScaffoldTowerCheck     scaffoldTowerCheck;
    private final TimerJitterCheck       timerJitterCheck;
    private final NoSlowDownCheck        noSlowDownCheck;
    private final FastEatCheck           fastEatCheck;
    private final FastBowCheck           fastBowCheck;
    private final AutoEatCheck           autoEatCheck;
    private final RegenCheck             regenCheck;
    private final AntiKnockbackCheck     antiKnockbackCheck;
    private final AimbotCheck            aimbotCheck;
    private final Reach3DCheck           reach3DCheck;
    private final LiquidJesusCheck       liquidJesusCheck;
    private final PhaseClipCheck         phaseClipCheck;
    private final NoSlowSneakCheck       noSlowSneakCheck;
    private final AutoArmorCheck         autoArmorCheck;
    private final AutoPotionCheck        autoPotionCheck;
    private final TracersCheck           tracersCheck;
    private final NoFallPacketCheck      noFallPacketCheck;

    private final EntitySnapshot entities;

    public PacketAnticheatListener(ArgusPlugin plugin, PacketDataStore store, EntitySnapshot entities) {
        super(PacketListenerPriority.NORMAL);
        this.plugin = plugin;
        this.store  = store;
        this.entities = entities;

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
        this.hitboxExpansionCheck = new HitboxExpansionCheck(plugin);
        this.backstabCheck        = new BackstabCheck(plugin);
        this.meleeFlyCheck        = new MeleeFlyCheck(plugin);
        this.blockGlitchCheck     = new BlockGlitchCheck(plugin);
        this.itemPickupCheck      = new ItemPickupCheck(plugin);
        this.inventoryTeleportCheck = new InventoryTeleportCheck(plugin);
        this.liquidWalkCheck      = new LiquidWalkCheck(plugin);
        this.chatMacroCheck       = new ChatMacroCheck(plugin);
        this.namedItemSpamCheck   = new NamedItemSpamCheck(plugin);
        this.autoClickerAdvancedCheck = new AutoClickerAdvancedCheck(plugin);

        this.killauraRotationCheck = new KillauraRotationCheck(plugin);
        this.killauraNoSwingCheck  = new KillauraNoSwingCheck(plugin);
        this.killauraThruWallCheck = new KillauraThruWallCheck(plugin);
        this.scaffoldRotationCheck = new ScaffoldRotationCheck(plugin);
        this.scaffoldTowerCheck    = new ScaffoldTowerCheck(plugin);
        this.timerJitterCheck      = new TimerJitterCheck(plugin);
        this.noSlowDownCheck       = new NoSlowDownCheck(plugin);
        this.fastEatCheck          = new FastEatCheck(plugin);
        this.fastBowCheck          = new FastBowCheck(plugin);
        this.autoEatCheck          = new AutoEatCheck(plugin);
        this.regenCheck            = new RegenCheck(plugin);
        this.antiKnockbackCheck    = new AntiKnockbackCheck(plugin);
        this.aimbotCheck           = new AimbotCheck(plugin);
        this.reach3DCheck          = new Reach3DCheck(plugin);
        this.liquidJesusCheck      = new LiquidJesusCheck(plugin);
        this.phaseClipCheck        = new PhaseClipCheck(plugin);
        this.noSlowSneakCheck      = new NoSlowSneakCheck(plugin);
        this.autoArmorCheck        = new AutoArmorCheck(plugin);
        this.autoPotionCheck       = new AutoPotionCheck(plugin);
        this.tracersCheck          = new TracersCheck(plugin);
        this.noFallPacketCheck     = new NoFallPacketCheck(plugin);
    }

    public FastEatCheck   getFastEatCheck()   { return fastEatCheck; }
    public AutoEatCheck   getAutoEatCheck()   { return autoEatCheck; }
    public FastBowCheck   getFastBowCheck()   { return fastBowCheck; }
    public RegenCheck     getRegenCheck()     { return regenCheck; }
    public AutoArmorCheck getAutoArmorCheck() { return autoArmorCheck; }
    public AutoPotionCheck getAutoPotionCheck() { return autoPotionCheck; }

    public CritCheck getCritCheck() { return critCheck; }
    public ProjectileAimCheck getProjectileAimCheck() { return projectileAimCheck; }
    public BowAimCheck getBowAimCheck() { return bowAimCheck; }
    public ItemPickupCheck getItemPickupCheck() { return itemPickupCheck; }
    public ChatMacroCheck getChatMacroCheck() { return chatMacroCheck; }
    public NamedItemSpamCheck getNamedItemSpamCheck() { return namedItemSpamCheck; }
    public PacketDataStore getStore() { return store; }

    public ViolationSink getSink() { return sink(); }
    public AutoTotemCheck getAutoTotemCheck() { return autoTotemCheck; }

    @Override
    public void onPacketPlayReceive(PacketPlayReceiveEvent event) {
        try {

            var ac = plugin.getAnticheatConfig();
            if (ac == null || !ac.isEnabled()) return;

            UUID uuid = event.getUser() != null ? event.getUser().getUUID() : null;
            if (uuid == null) return;

            Player player = Bukkit.getPlayer(uuid);
            if (player == null) return;
            if (player.hasPermission("argus.ac.bypass")) return;

            PacketDataStore.State s = store.get(uuid);

            var type = event.getPacketType();

            if (s.pendingSwingTarget != null && type != PacketType.Play.Client.ANIMATION) {
                resolvePendingSwing(player, s);
            }

            if (type == PacketType.Play.Client.PLAYER_POSITION
                || type == PacketType.Play.Client.PLAYER_POSITION_AND_ROTATION
                || type == PacketType.Play.Client.PLAYER_ROTATION
                || type == PacketType.Play.Client.PLAYER_FLYING) {

                long now = System.currentTimeMillis();

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

                        s.pushMove(now);
                        timerCheck.handlePositionPacket(player, s, now, sink());

                        phaseCheck.handlePositionPacket(player, s, nx, ny, nz, sink());

                        velocityCheck.handlePositionPacket(player, s, nx, ny, nz, sink());

                        vclipCheck.handlePositionPacket(player, s, nx, ny, nz, sink());

                        stepCheck.handlePositionPacket(player, s, nx, ny, nz, nowOnGround, sink());

                        speedPacketCheck.handlePositionPacket(player, s, nx, ny, nz, now, nowOnGround, sink());

                        boatFlyCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());
                        jetpackCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());
                        spiderCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        multiVelocityCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        boatFlyAdvancedCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());

                        inventoryTeleportCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());
                        liquidWalkCheck.handlePositionPacket(player, s, nx, ny, nz, sink());

                        timerJitterCheck.handlePositionPacket(player, s, now, sink());
                        noSlowDownCheck.handlePositionPacket(player, s, nx, nz, now, sink());
                        antiKnockbackCheck.handlePositionPacket(player, s, nx, nz, now, sink());
                        noSlowSneakCheck.handlePositionPacket(player, s, nx, nz, now, sink());
                        liquidJesusCheck.handlePositionPacket(player, s, nx, ny, nz, sink());
                        phaseClipCheck.handlePositionPacket(player, s, nx, ny, nz, now, sink());
                        noFallPacketCheck.handlePositionPacket(player, s, nx, ny, nz, nowOnGround, sink());

                        s.lastDeltaY = ny - s.lastY;
                        s.lastHorizMove = Math.hypot(nx - s.lastX, nz - s.lastZ);
                        s.lastX = nx;
                        s.lastY = ny;
                        s.lastZ = nz;
                        s.lastMoveMs = now;
                    }
                    if (wrap.hasRotationChanged() && s.rotationResyncPending) {
                        // Primer paquete tras confirmar un teleport: la rotacion la impuso el server.
                        s.rotationResyncPending = false;
                        s.lastYaw   = wrap.getLocation().getYaw();
                        s.lastPitch = wrap.getLocation().getPitch();
                    } else if (wrap.hasRotationChanged()) {
                        float ny  = wrap.getLocation().getYaw();
                        float npi = wrap.getLocation().getPitch();

                        invalidRotationCheck.handleRotation(player, s, ny, npi, sink());

                        aimSnapCheck.handleRotation(player, s, ny, npi, sink());

                        s.pushRotation(ny, npi, now);
                        s.prevYaw   = s.lastYaw;
                        s.prevPitch = s.lastPitch;
                        s.lastYaw   = ny;
                        s.lastPitch = npi;

                        killauraRotationCheck.handleRotation(player, s, ny, npi, now, sink());
                        tracersCheck.handleRotation(player, s, entities.invisiblePlayers(), sink());
                    }
                }

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

                    Entity target = entities.byId(wrap.getEntityId());

                    if (target != null && target.isValid()) {
                        double lagComp = entities.lagAllowance(target, s.pingMs);
                        reachCheck.handleAttack(player, target, s, lagComp, sink());
                        // 1.9+ manda el swing DESPUES del ataque: se evalua con el paquete siguiente.
                        s.pendingSwingTarget = target;
                        s.pendingAttackMs = now;

                        killauraAimCheck.handleAttack(player, target, s, now, sink());
                        killauraBlockingCheck.handleAttack(player, target, s, now, sink());
                        hitboxExpansionCheck.handleAttack(player, target, s, sink());
                        backstabCheck.handleAttack(player, target, s, sink());
                        meleeFlyCheck.handleAttack(player, target, s, now, sink());

                        killauraThruWallCheck.handleAttack(player, target, s, sink());
                        aimbotCheck.handleAttack(player, target, entities.all(), s, sink());
                        reach3DCheck.handleAttack(player, target, s, lagComp, sink());
                    }

                    plugin.getAutoClickEngine().onAttack(player, now, v ->
                        Bukkit.getScheduler().runTask(plugin, () ->
                            plugin.getViolationManager().flag(v)));
                }

            } else if (type == PacketType.Play.Client.ANIMATION) {
                long now = System.currentTimeMillis();
                s.lastSwingMs = now;
                s.pushSwing(now);
                swingCheck.handleSwing(player, s, now, sink());
                if (s.pendingSwingTarget != null) resolvePendingSwing(player, s);
                plugin.getAutoClickEngine().onSwing(player, now, v ->
                    Bukkit.getScheduler().runTask(plugin, () ->
                        plugin.getViolationManager().flag(v)));

            } else if (type == PacketType.Play.Client.TELEPORT_CONFIRM) {
                s.rotationResyncPending = true;

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

                try {
                    var wrapP = new com.github.retrooper.packetevents.wrapper.play.client
                        .WrapperPlayClientPlayerBlockPlacement(event);
                    var pos = wrapP.getBlockPosition();
                    if (pos != null) {
                        blockReachCheck.handleBlockInteract(player, s, pos.getX(), pos.getY(), pos.getZ(), sink());
                        blockGlitchCheck.handleBlockInteract(player, s, pos.getX(), pos.getY(), pos.getZ(), sink());

                        scaffoldRotationCheck.handleBlockPlacement(player, s, pos.getX(), pos.getY(), pos.getZ(), now, sink());
                        var cur = wrapP.getCursorPosition();
                        if (cur != null) {
                            scaffoldRotationCheck.handlePlacementAim(player, s, pos.getX() + cur.getX(),
                                pos.getY() + cur.getY(), pos.getZ() + cur.getZ(), sink());
                        }
                        scaffoldTowerCheck.handleBlockPlacement(player, s, pos.getX(), pos.getY(), pos.getZ(), now, sink());
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
                        blockGlitchCheck.handleBlockInteract(player, s, pos.getX(), pos.getY(), pos.getZ(), sink());
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

            plugin.getLogger().fine(() -> "[Argus/Packet] receive err: "
                + t.getClass().getSimpleName() + " " + t.getMessage());
        }
    }

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

    /** Si hubo swing antes (1.8) o justo despues (1.9+) del ataque, lastSwingMs queda cerca de pendingAttackMs. */
    private void resolvePendingSwing(Player player, PacketDataStore.State s) {
        Entity target = s.pendingSwingTarget;
        long at = s.pendingAttackMs;
        s.pendingSwingTarget = null;
        if (target == null) return;
        long effectiveNow = s.lastSwingMs >= at ? s.lastSwingMs : at;
        swingCheck.handleAttack(player, target, s, effectiveNow, sink());
        killauraNoSwingCheck.handleAttack(player, target, s, effectiveNow, sink());
    }

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

    private ViolationSink sink() {
        return v -> {
            if (v == null) return;

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
