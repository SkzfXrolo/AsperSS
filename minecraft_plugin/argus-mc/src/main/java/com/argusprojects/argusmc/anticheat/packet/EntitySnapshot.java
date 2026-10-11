package com.argusprojects.argusmc.anticheat.packet;

import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.entity.Entity;
import org.bukkit.entity.Player;
import org.bukkit.potion.PotionEffectType;

import java.util.ArrayList;
import java.util.Collection;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

/**
 * Entidades cerca de cada jugador, reconstruido en el main thread cada tick.
 * Los handlers de paquetes corren en hilos de Netty y Paper rechaza
 * getEntities()/getNearbyEntities() fuera del main thread (AsyncCatcher),
 * asi que leen de aca en vez de tocar el World.
 */
public final class EntitySnapshot implements Runnable {

    static final double ATTACK_RADIUS = 8.0;
    /** Ticks que el cliente ve atrasadas a otras entidades por interpolacion, ademas del ping. */
    /** El cliente 1.8 interpola 3 ticks + el golpe sale al tick siguiente del que vio. */
    static final double INTERPOLATION_TICKS = 4;
    /** Tope alto: solo se usa si el objetivo realmente se movio tanto (speed, knockback, montura). */
    static final double MAX_LAG_ALLOWANCE = 2.5;

    private volatile Map<Integer, Entity> byId = Map.of();
    private volatile Map<Integer, Double> movedPerTick = Map.of();
    private volatile List<Player> invisiblePlayers = List.of();
    private Map<Integer, double[]> lastPos = new HashMap<>();

    @Override
    public void run() {
        Map<Integer, Entity> ids = new HashMap<>();
        List<Player> invisible = new ArrayList<>();
        for (Player p : Bukkit.getOnlinePlayers()) {
            ids.put(p.getEntityId(), p);
            if (p.isInvisible() || p.hasPotionEffect(PotionEffectType.INVISIBILITY)) {
                invisible.add(p);
            }
            for (Entity e : p.getNearbyEntities(ATTACK_RADIUS, ATTACK_RADIUS, ATTACK_RADIUS)) {
                ids.put(e.getEntityId(), e);
            }
        }
        Map<Integer, double[]> pos = new HashMap<>(ids.size() * 2);
        Map<Integer, Double> moved = new HashMap<>(ids.size() * 2);
        for (Map.Entry<Integer, Entity> en : ids.entrySet()) {
            Location l = en.getValue().getLocation();
            double[] now = {l.getX(), l.getY(), l.getZ()};
            pos.put(en.getKey(), now);
            double[] prev = lastPos.get(en.getKey());
            if (prev != null) {
                double dx = now[0] - prev[0], dy = now[1] - prev[1], dz = now[2] - prev[2];
                // Pico reciente que decae ~5 ticks: el cliente ve al objetivo interpolado 2-3 ticks
                // atras, asi que si recien freno todavia hay que tolerar su movimiento anterior.
                double m = Math.sqrt(dx * dx + dy * dy + dz * dz);
                moved.put(en.getKey(), Math.max(m, movedPerTick.getOrDefault(en.getKey(), 0.0) * 0.8));
            }
        }
        lastPos = pos;
        byId = ids;
        movedPerTick = moved;
        invisiblePlayers = invisible;
    }

    public Entity byId(int entityId) {
        return byId.get(entityId);
    }

    public Collection<Entity> all() {
        return byId.values();
    }

    public List<Player> invisiblePlayers() {
        return invisiblePlayers;
    }

    /**
     * Cuanto puede diferir la posicion que el atacante VE del objetivo respecto de la que tiene
     * el server: el objetivo se sigue moviendo durante el ping + la interpolacion del cliente.
     */
    public double lagAllowance(Entity target, long attackerPingMs) {
        Double moved = movedPerTick.get(target.getEntityId());
        if (moved == null) return 0.0;
        double ticks = Math.max(0L, attackerPingMs) / 50.0 + INTERPOLATION_TICKS;
        return Math.min(MAX_LAG_ALLOWANCE, moved * ticks);
    }
}
