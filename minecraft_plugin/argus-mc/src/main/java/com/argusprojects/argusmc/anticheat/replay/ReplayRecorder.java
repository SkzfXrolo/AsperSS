package com.argusprojects.argusmc.anticheat.replay;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationFormatter;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import com.argusprojects.argusmc.util.Messages;
import org.bukkit.Bukkit;
import org.bukkit.Location;
import org.bukkit.Material;
import org.bukkit.World;
import org.bukkit.entity.Entity;
import org.bukkit.entity.LivingEntity;
import org.bukkit.entity.Player;

import java.io.IOException;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.text.SimpleDateFormat;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.Date;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ConcurrentLinkedQueue;

/**
 * Graba los ultimos segundos de todos los jugadores (y mobs cercanos) para que cada alerta MID+
 * deje una prueba: un .html autocontenido con un replay 3D (posiciones, giros, golpes con su
 * distancia real, bloques de alrededor) que se puede reproducir y exportar como video.
 *
 * Posiciones/bloques se leen en el hilo principal (cada tick); los golpes/swings llegan desde el
 * hilo de paquetes por una cola concurrente.
 */
public final class ReplayRecorder implements Runnable {

    private static final long KEEP_MS = 25_000L;
    private static final long BEFORE_MS = 15_000L;
    private static final long AFTER_MS = 5_000L;
    private static final long CAPTURE_COOLDOWN_MS = 45_000L;
    private static final double NEARBY = 32.0;
    private static final double MOB_RADIUS = 8.0;
    private static final int MAX_BLOCKS = 40_000;

    /** t, x, y, z, yaw, pitch, flags (1 suelo, 2 agachado, 4 sprint). */
    private record Frame(long t, double x, double y, double z, float yaw, float pitch, int flags) {}

    /** type: A ataque, S swing, P coloca, D rompe. */
    private record Event(long t, int entityId, char type, int targetId, double x, double y, double z, double dist) {}

    private static final class Track {
        final String name;
        final String type;
        final boolean player;
        final ArrayDeque<Frame> frames = new ArrayDeque<>();
        Track(String name, String type, boolean player) { this.name = name; this.type = type; this.player = player; }
    }

    private static final class Capture {
        final Violation trigger;
        final long startMs, endMs;
        final List<Violation> violations = new ArrayList<>();
        Capture(Violation v, long now) { trigger = v; startMs = now - BEFORE_MS; endMs = now + AFTER_MS; violations.add(v); }
    }

    private final ArgusPlugin plugin;
    private final Map<Integer, Track> tracks = new HashMap<>();
    private final ArrayDeque<Event> events = new ArrayDeque<>();
    private final ConcurrentLinkedQueue<Event> incoming = new ConcurrentLinkedQueue<>();
    private final Map<UUID, Capture> pending = new HashMap<>();
    private final Map<UUID, Long> lastCapture = new ConcurrentHashMap<>();
    private final Map<UUID, Path> lastFile = new ConcurrentHashMap<>();

    public ReplayRecorder(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    // ------------------------------------------------------------ eventos (hilo de paquetes)

    public void attack(Player p, Entity target, double dist) {
        Location l = target.getLocation();
        incoming.add(new Event(System.currentTimeMillis(), p.getEntityId(), 'A', target.getEntityId(), l.getX(), l.getY(), l.getZ(), dist));
    }

    public void swing(Player p) {
        incoming.add(new Event(System.currentTimeMillis(), p.getEntityId(), 'S', 0, 0, 0, 0, 0));
    }

    public void place(Player p, int x, int y, int z) {
        incoming.add(new Event(System.currentTimeMillis(), p.getEntityId(), 'P', 0, x, y, z, 0));
    }

    public void dig(Player p, int x, int y, int z) {
        incoming.add(new Event(System.currentTimeMillis(), p.getEntityId(), 'D', 0, x, y, z, 0));
    }

    /** Ultima prueba guardada de este jugador (para adjuntar al ban). */
    public Path lastEvidence(UUID uuid) {
        return lastFile.get(uuid);
    }

    // ------------------------------------------------------------ alertas (hilo principal)

    public void onViolation(Violation v) {
        if (v.level.ordinal() < ViolationLevel.MID.ordinal()) return;
        Capture c = pending.get(v.playerUuid);
        if (c != null) {
            c.violations.add(v);
            return;
        }
        long now = System.currentTimeMillis();
        Long last = lastCapture.get(v.playerUuid);
        if (last != null && now - last < CAPTURE_COOLDOWN_MS) return;
        lastCapture.put(v.playerUuid, now);
        pending.put(v.playerUuid, new Capture(v, now));
    }

    // ------------------------------------------------------------ tick

    @Override
    public void run() {
        long now = System.currentTimeMillis();
        for (Event e; (e = incoming.poll()) != null; ) events.addLast(e);
        while (!events.isEmpty() && now - events.peekFirst().t() > KEEP_MS) events.pollFirst();

        Map<Integer, Boolean> seen = new HashMap<>();
        for (Player p : Bukkit.getOnlinePlayers()) {
            record(p, now, true);
            seen.put(p.getEntityId(), true);
            for (Entity e : p.getNearbyEntities(MOB_RADIUS, MOB_RADIUS, MOB_RADIUS)) {
                if (e instanceof LivingEntity && !(e instanceof Player) && seen.put(e.getEntityId(), true) == null) {
                    record(e, now, false);
                }
            }
        }
        tracks.values().removeIf(t -> {
            while (!t.frames.isEmpty() && now - t.frames.peekFirst().t() > KEEP_MS) t.frames.pollFirst();
            return t.frames.isEmpty();
        });

        if (pending.isEmpty()) return;
        var it = pending.entrySet().iterator();
        while (it.hasNext()) {
            var en = it.next();
            if (now < en.getValue().endMs) continue;
            it.remove();
            try {
                save(en.getKey(), en.getValue());
            } catch (Throwable t) {
                plugin.getLogger().warning("[Argus/Replay] no se pudo guardar la prueba: " + t.getMessage());
            }
        }
    }

    private void record(Entity e, long now, boolean isPlayer) {
        Track t = tracks.computeIfAbsent(e.getEntityId(), k -> new Track(
            isPlayer ? e.getName() : e.getType().name().toLowerCase(Locale.ROOT),
            e.getType().name().toLowerCase(Locale.ROOT), isPlayer));
        Location l = e.getLocation();
        int flags = (e.isOnGround() ? 1 : 0);
        if (e instanceof Player p) flags |= (p.isSneaking() ? 2 : 0) | (p.isSprinting() ? 4 : 0);
        t.frames.addLast(new Frame(now, l.getX(), l.getY(), l.getZ(), l.getYaw(), l.getPitch(), flags));
    }

    // ------------------------------------------------------------ guardado

    private void save(UUID suspectUuid, Capture c) throws IOException {
        Player suspect = Bukkit.getPlayer(suspectUuid);
        Track st = null;
        int suspectId = -1;
        for (var en : tracks.entrySet()) {
            if (en.getValue().player && en.getValue().name.equals(c.trigger.playerName)) { st = en.getValue(); suspectId = en.getKey(); }
        }
        if (st == null) return;
        List<Frame> sframes = within(st, c);
        if (sframes.isEmpty()) return;

        double ox = Math.floor(sframes.get(0).x()), oy = Math.floor(sframes.get(0).y()), oz = Math.floor(sframes.get(0).z());
        StringBuilder sb = new StringBuilder(64 * 1024);
        sb.append('{');
        sb.append("\"meta\":{")
          .append("\"player\":").append(q(c.trigger.playerName))
          .append(",\"hack\":").append(q(ViolationFormatter.checkLabel(c.trigger.checkName)))
          .append(",\"level\":").append(q(c.trigger.level.name()))
          .append(",\"server\":").append(q(Bukkit.getServer().getName() + " " + Bukkit.getMinecraftVersion()))
          .append(",\"world\":").append(q(suspect != null ? suspect.getWorld().getName() : ""))
          .append(",\"flagMs\":").append(c.trigger.timestampMs)
          .append(",\"startMs\":").append(c.startMs).append(",\"endMs\":").append(c.endMs)
          .append(",\"origin\":[").append((long) ox).append(',').append((long) oy).append(',').append((long) oz).append("]")
          .append(",\"suspectId\":").append(suspectId)
          .append("},");

        sb.append("\"violations\":[");
        for (int i = 0; i < c.violations.size(); i++) {
            Violation v = c.violations.get(i);
            if (i > 0) sb.append(',');
            sb.append("{\"t\":").append(v.timestampMs)
              .append(",\"label\":").append(q(ViolationFormatter.checkLabel(v.checkName)))
              .append(",\"check\":").append(q(v.checkName))
              .append(",\"level\":").append(q(v.level.name()))
              .append(",\"details\":").append(q(ViolationFormatter.formatSummary(v.checkName, v.details)))
              .append('}');
        }
        sb.append("],");

        // Pistas: el sospechoso + todo lo que estuvo cerca durante la ventana.
        sb.append("\"tracks\":{");
        boolean first = true;
        for (var en : tracks.entrySet()) {
            List<Frame> fs = within(en.getValue(), c);
            if (fs.isEmpty() || !near(fs, sframes)) continue;
            if (!first) sb.append(',');
            first = false;
            Track t = en.getValue();
            sb.append('"').append(en.getKey()).append("\":{\"name\":").append(q(t.name))
              .append(",\"type\":").append(q(t.type)).append(",\"player\":").append(t.player).append(",\"frames\":[");
            for (int i = 0; i < fs.size(); i++) {
                Frame f = fs.get(i);
                if (i > 0) sb.append(',');
                sb.append('[').append(f.t() - c.startMs).append(',').append(r(f.x() - ox)).append(',').append(r(f.y() - oy))
                  .append(',').append(r(f.z() - oz)).append(',').append(r(f.yaw())).append(',').append(r(f.pitch()))
                  .append(',').append(f.flags()).append(']');
            }
            sb.append("]}");
        }
        sb.append("},");

        sb.append("\"events\":[");
        first = true;
        for (Event e : events) {
            if (e.t() < c.startMs || e.t() > c.endMs) continue;
            if (!first) sb.append(',');
            first = false;
            sb.append('[').append(e.t() - c.startMs).append(',').append(e.entityId()).append(",\"").append(e.type()).append("\",")
              .append(e.targetId()).append(',').append(r(e.x() - ox)).append(',').append(r(e.y() - oy)).append(',')
              .append(r(e.z() - oz)).append(',').append(r(e.dist())).append(']');
        }
        sb.append("],");

        appendBlocks(sb, suspect != null ? suspect.getWorld() : Bukkit.getWorlds().get(0), sframes, (int) ox, (int) oy, (int) oz);
        sb.append('}');

        String json = sb.toString();
        String fileName = new SimpleDateFormat("yyyyMMdd-HHmmss").format(new Date(c.trigger.timestampMs))
            + "_" + ViolationFormatter.checkLabel(c.trigger.checkName).replaceAll("[^A-Za-z0-9]", "") + ".html";
        Path dir = plugin.getDataFolder().toPath().resolve("evidence").resolve(c.trigger.playerName);
        Path file = dir.resolve(fileName);
        lastFile.put(suspectUuid, file);
        String playerName = c.trigger.playerName;
        Bukkit.getScheduler().runTaskAsynchronously(plugin, () -> {
            try {
                Files.createDirectories(dir);
                Files.writeString(file, viewer().replace("\"__REPLAY_DATA__\"", json), StandardCharsets.UTF_8);
                Bukkit.getScheduler().runTask(plugin, () -> announce(playerName, file));
            } catch (IOException ex) {
                plugin.getLogger().warning("[Argus/Replay] " + ex.getMessage());
            }
        });
    }

    private void announce(String player, Path file) {
        String rel = plugin.getDataFolder().toPath().relativize(file).toString().replace('\\', '/');
        String line = Messages.color("&8▎&b&lARGUS &8» &7Prueba guardada de &f" + player + "&7: &f" + rel);
        for (Player p : Bukkit.getOnlinePlayers()) if (p.hasPermission("argus.alerts")) p.sendMessage(line);
        plugin.getLogger().info("[Argus/Replay] prueba guardada: " + file);
    }

    private static List<Frame> within(Track t, Capture c) {
        List<Frame> out = new ArrayList<>();
        for (Frame f : t.frames) if (f.t() >= c.startMs && f.t() <= c.endMs) out.add(f);
        return out;
    }

    private static boolean near(List<Frame> a, List<Frame> suspect) {
        Frame s0 = suspect.get(suspect.size() / 2);
        for (Frame f : a) {
            if (Math.abs(f.x() - s0.x()) < NEARBY && Math.abs(f.z() - s0.z()) < NEARBY && Math.abs(f.y() - s0.y()) < NEARBY) return true;
        }
        return false;
    }

    /** Bloques visibles (con al menos una cara al aire) alrededor del recorrido del sospechoso. */
    private static void appendBlocks(StringBuilder sb, World w, List<Frame> path, int ox, int oy, int oz) {
        int minX = Integer.MAX_VALUE, minY = Integer.MAX_VALUE, minZ = Integer.MAX_VALUE;
        int maxX = Integer.MIN_VALUE, maxY = Integer.MIN_VALUE, maxZ = Integer.MIN_VALUE;
        for (Frame f : path) {
            minX = Math.min(minX, (int) Math.floor(f.x())); maxX = Math.max(maxX, (int) Math.floor(f.x()));
            minY = Math.min(minY, (int) Math.floor(f.y())); maxY = Math.max(maxY, (int) Math.floor(f.y()));
            minZ = Math.min(minZ, (int) Math.floor(f.z())); maxZ = Math.max(maxZ, (int) Math.floor(f.z()));
        }
        minX -= 10; maxX += 10; minZ -= 10; maxZ += 10; minY -= 5; maxY += 8;
        minY = Math.max(minY, w.getMinHeight()); maxY = Math.min(maxY, w.getMaxHeight() - 1);
        Map<Material, Integer> palette = new LinkedHashMap<>();
        StringBuilder data = new StringBuilder();
        int count = 0;
        outer:
        for (int x = minX; x <= maxX; x++) for (int z = minZ; z <= maxZ; z++) for (int y = minY; y <= maxY; y++) {
            Material m = w.getBlockAt(x, y, z).getType();
            // Solo solidos y liquidos: plantas/enredaderas/telaranas como cubos ensucian el replay.
            if (!m.isSolid() && m != Material.WATER && m != Material.LAVA) continue;
            if (!exposed(w, x, y, z)) continue;
            int idx = palette.computeIfAbsent(m, k -> palette.size());
            if (count > 0) data.append(',');
            data.append(x - ox).append(',').append(y - oy).append(',').append(z - oz).append(',').append(idx);
            if (++count >= MAX_BLOCKS) break outer;
        }
        sb.append("\"blocks\":{\"palette\":[");
        int i = 0;
        for (Material m : palette.keySet()) {
            if (i++ > 0) sb.append(',');
            sb.append(q(m.name().toLowerCase(Locale.ROOT)));
        }
        sb.append("],\"data\":[").append(data).append("]}");
    }

    private static boolean exposed(World w, int x, int y, int z) {
        return !w.getBlockAt(x + 1, y, z).getType().isOccluding() || !w.getBlockAt(x - 1, y, z).getType().isOccluding()
            || !w.getBlockAt(x, y + 1, z).getType().isOccluding() || !w.getBlockAt(x, y - 1, z).getType().isOccluding()
            || !w.getBlockAt(x, y, z + 1).getType().isOccluding() || !w.getBlockAt(x, y, z - 1).getType().isOccluding();
    }

    private String viewerCache;

    private String viewer() throws IOException {
        if (viewerCache == null) {
            try (InputStream in = plugin.getResource("replay/viewer.html")) {
                if (in == null) throw new IOException("falta replay/viewer.html en el jar");
                viewerCache = new String(in.readAllBytes(), StandardCharsets.UTF_8);
            }
        }
        return viewerCache;
    }

    private static String r(double v) {
        return String.format(Locale.ROOT, "%.3f", v);
    }

    static String q(String s) {
        if (s == null) return "\"\"";
        StringBuilder b = new StringBuilder(s.length() + 2).append('"');
        for (char ch : s.toCharArray()) {
            switch (ch) {
                case '"' -> b.append("\\\"");
                case '\\' -> b.append("\\\\");
                case '\n' -> b.append("\\n");
                case '<' -> b.append("\\u003c");   // nada de </script> dentro del html
                default -> { if (ch < 0x20) b.append(String.format("\\u%04x", (int) ch)); else b.append(ch); }
            }
        }
        return b.append('"').toString();
    }
}
