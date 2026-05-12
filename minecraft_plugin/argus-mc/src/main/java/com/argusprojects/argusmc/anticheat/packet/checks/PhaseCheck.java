package com.argusprojects.argusmc.anticheat.packet.checks;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.anticheat.packet.PacketAnticheatListener.ViolationSink;
import com.argusprojects.argusmc.anticheat.packet.PacketDataStore;
import org.bukkit.Material;
import org.bukkit.entity.Player;

/**
 * Pack 47 — Phase / NoClip.
 *
 * <p>Detecta cuando el cliente envia un PlayerPosition que cruza un bloque
 * solido entre packet anterior y actual. Bukkit no expone esto: el server
 * "corrige" la posicion antes de que PlayerMoveEvent dispare, ocultando el
 * intento. A nivel packet vemos el movimiento RAW.
 *
 * <p>Algoritmo: si el delta XYZ atraviesa una celda cuyo bloque es
 * {@code !isPassable()} y NO esta en gamemode SPECTATOR/CREATIVE flying,
 * disparamos HIGH. Para minimizar FPs con escaleras / slabs / glass panes,
 * usamos una whitelist conservadora de bloques "atravesables imposibles":
 * stone, obsidian, bedrock, planks, cobblestone, wool. El resto no flagea.
 */
public final class PhaseCheck {

    private final ArgusPlugin plugin;

    public PhaseCheck(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void handlePositionPacket(Player player, PacketDataStore.State s,
                                     double nx, double ny, double nz,
                                     ViolationSink sink) {
        if (!plugin.getAnticheatConfig().isCheckEnabled("phase")) return;
        if (s.teleporting) return;
        if (player.getAllowFlight() && player.isFlying()) return;
        if (player.getGameMode() == org.bukkit.GameMode.SPECTATOR) return;
        if (player.getGameMode() == org.bukkit.GameMode.CREATIVE) return;
        if (s.lastX == 0 && s.lastY == 0 && s.lastZ == 0) return; // sin baseline aun

        double dx = nx - s.lastX;
        double dy = ny - s.lastY;
        double dz = nz - s.lastZ;
        double dist2 = dx * dx + dy * dy + dz * dz;
        // Movimiento < 1 bloque/packet no tiene riesgo de phase.
        if (dist2 < 1.0) return;
        // > 12 bloques en un packet ya lo detecta otra check (speed/teleport).
        if (dist2 > 144.0) return;

        // Sampleamos puntos intermedios entre last y new (raycast simple).
        int steps = Math.max(2, (int) Math.ceil(Math.sqrt(dist2) * 2));
        org.bukkit.World w = player.getWorld();
        int blockedSteps = 0;
        for (int i = 1; i < steps; i++) {
            double t = (double) i / steps;
            double sx = s.lastX + dx * t;
            double sy = s.lastY + dy * t + 1.0; // ~ a la altura del torso
            double sz = s.lastZ + dz * t;
            Material m = w.getBlockAt((int) Math.floor(sx), (int) Math.floor(sy), (int) Math.floor(sz)).getType();
            if (isHardSolid(m)) blockedSteps++;
        }

        // Si >= 2 muestras intermedias chocaron contra solidos hard, es phase claro.
        if (blockedSteps >= 2) {
            sink.flag(new Violation(player, "phase_packet",
                ViolationLevel.HIGH,
                String.format("dx=%.2f dy=%.2f dz=%.2f blockedSamples=%d/%d", dx, dy, dz, blockedSteps, steps - 1)));
        }
    }

    private static boolean isHardSolid(Material m) {
        if (m == null || m.isAir()) return false;
        switch (m) {
            case STONE: case DEEPSLATE: case COBBLESTONE: case BEDROCK: case OBSIDIAN:
            case OAK_PLANKS: case BIRCH_PLANKS: case SPRUCE_PLANKS: case JUNGLE_PLANKS:
            case ACACIA_PLANKS: case DARK_OAK_PLANKS: case CHERRY_PLANKS: case CRIMSON_PLANKS: case WARPED_PLANKS:
            case WHITE_WOOL: case BLACK_WOOL: case GRAY_WOOL: case RED_WOOL: case GREEN_WOOL:
            case BLUE_WOOL: case YELLOW_WOOL: case ORANGE_WOOL: case PURPLE_WOOL: case PINK_WOOL:
            case BROWN_WOOL: case CYAN_WOOL: case LIGHT_BLUE_WOOL: case LIGHT_GRAY_WOOL:
            case LIME_WOOL: case MAGENTA_WOOL:
            case IRON_BLOCK: case GOLD_BLOCK: case DIAMOND_BLOCK: case NETHERITE_BLOCK:
            case COAL_BLOCK: case EMERALD_BLOCK: case LAPIS_BLOCK: case REDSTONE_BLOCK:
                return true;
            default:
                return false;
        }
    }
}
