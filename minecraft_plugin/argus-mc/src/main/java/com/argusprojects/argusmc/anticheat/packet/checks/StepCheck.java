package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.GameMode;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

/**
 * Pack 48 #483 — StepCheck (Step / Spider variants).
 *
 * <p>Step hack permite subir un bloque entero sin saltar — el cliente envia
 * un PlayerPosition con dy ≈ +1.0 estando previamente en {@code onGround=true},
 * cuando lo unico vanilla es subir slabs/stairs (dy &lt;= +0.5) o saltar
 * (curva de salto: dy inicial = +0.42, decreciente).
 *
 * <p>Diferencia con VClipCheck: este apunta especificamente al "step desde
 * suelo" — dy entre ~+0.95 y ~+1.05 partiendo de on-ground. VClip dispara
 * para dy &gt; 0.65 en cualquier estado. Step tiene mucho menor false-positive
 * porque exige el patron exacto (vanilla con jump boost N todavia sigue una
 * curva, no produce un step plano de +1.0).
 */
public final class StepCheck {

    /** Ventana maxima desde el ultimo onGround para considerar que "venia del suelo". */
    private static final long FROM_GROUND_WINDOW_MS = 120L;

    private final ArgusPlugin plugin;

    public StepCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     boolean nowOnGround,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("step")) return;
        if (s.teleporting) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return;

        GameMode gm = player.getGameMode();
        if (gm == GameMode.CREATIVE || gm == GameMode.SPECTATOR) return;
        if (player.getAllowFlight() && player.isFlying()) return;
        if (player.isInsideVehicle()) return;
        if (player.isGliding()) return;
        if (player.isClimbing()) return;
        if (player.isSwimming()) return;
        if (player.isInWater()) return;

        double dy = ny - s.lastY;
        long now = System.currentTimeMillis();

        ConfigurationSection sec = plugin.getAnticheatConfig().checkSection("step");
        double minDy = sec != null ? sec.getDouble("min_dy", 0.95) : 0.95;
        double maxDy = sec != null ? sec.getDouble("max_dy", 1.10) : 1.10;
        long groundWindow = sec != null ? sec.getLong("from_ground_window_ms", FROM_GROUND_WINDOW_MS) : FROM_GROUND_WINDOW_MS;

        // Step solo aplica al PRIMER packet que sube — el siguiente ya empieza
        // a tener dy decreciente por gravedad incluso con cheats.
        if (dy < minDy || dy > maxDy) return;
        // Tenia que estar en piso muy reciente.
        if (!s.lastOnGround || (now - s.lastOnGroundMs) > groundWindow) return;
        // Si esta cayendo (lastDeltaY < -0.1) no es step todavia, esto puede
        // ser una correccion del server.
        if (s.lastDeltaY < -0.1) return;

        // Para minimizar FP: no flagear si el cliente esta arriba de stairs/slabs
        // (legitimo). Verificamos con el bloque inmediato bajo la new pos.
        try {
            org.bukkit.block.Block below = player.getWorld().getBlockAt(
                (int) Math.floor(nx), (int) Math.floor(ny - 0.02), (int) Math.floor(nz));
            String name = below.getType().name();
            // Falsa alarma legitima: subir stairs/slabs es naturalmente posible
            // pero no produce dy=+1.0 (produce ~+0.5). Si el bloque ES stairs/slab,
            // que el step venga de hacks por encima de el — no relajamos.
            if (name.contains("BUBBLE_COLUMN") || name.contains("SCAFFOLDING")
                || name.contains("WATER") || name.contains("LAVA")
                || name.contains("HONEY_BLOCK") || name.contains("SLIME_BLOCK")) {
                return;
            }
        } catch (Throwable ignored) {
        }

        ViolationLevel lvl = (dy >= 1.00) ? ViolationLevel.HIGH : ViolationLevel.MID;
        sink.flag(new Violation(player, "step_packet",
            lvl,
            String.format("dy=%.3f from_ground_age=%dms", dy, now - s.lastOnGroundMs)));
    }
}
