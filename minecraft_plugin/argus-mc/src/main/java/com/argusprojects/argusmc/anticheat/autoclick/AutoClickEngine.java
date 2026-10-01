package com.argusprojects.argusmc.anticheat.autoclick;

import com.argusprojects.argusmc.ArgusPlugin;
import com.argusprojects.argusmc.anticheat.AnticheatConfig;
import com.argusprojects.argusmc.anticheat.Violation;
import com.argusprojects.argusmc.anticheat.ViolationLevel;
import org.bukkit.configuration.ConfigurationSection;
import org.bukkit.entity.Player;

import java.util.Locale;
import java.util.Map;
import java.util.UUID;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.Consumer;

public final class AutoClickEngine {

    private static final long DEDUPE_MS = 4L;
    private static final long ANALYZE_COOLDOWN_MS = 40L;
    private static final long PLACE_SWING_MS = 80L;
    /** Una rafaga en 250ms sin CPS sostenido es red agrupando paquetes (tunel, wifi), no un clicker. */
    private static final int BURST_MIN_SUSTAINED_CPS = 15;

    private final ArgusPlugin plugin;
    private final Map<UUID, PlayerClickState> states = new ConcurrentHashMap<>();

    public AutoClickEngine(ArgusPlugin plugin) {
        this.plugin = plugin;
    }

    public void remove(UUID uuid) {
        states.remove(uuid);
    }

    public void onSwing(Player player, long now, Consumer<Violation> sink) {
        if (player == null || sink == null) {
            return;
        }
        if (!isEnabled()) {
            return;
        }
        PlayerClickState s = state(player.getUniqueId());
        // 1.8 manda swing al poner/usar un bloque: construir rapido no es clickear.
        if (now - s.lastPlaceMs < PLACE_SWING_MS) {
            return;
        }
        if (now - s.lastSwingRecordedMs < DEDUPE_MS) {
            return;
        }
        s.lastSwingRecordedMs = now;
        s.swings.push(now);
        analyze(player, s, now, sink);
    }

    public void onPlace(UUID uuid, long now) {
        state(uuid).lastPlaceMs = now;
    }

    public void onAttack(Player player, long now, Consumer<Violation> sink) {
        if (player == null || sink == null) {
            return;
        }
        if (!isEnabled()) {
            return;
        }
        PlayerClickState s = state(player.getUniqueId());
        if (now - s.lastAttackRecordedMs < DEDUPE_MS) {
            return;
        }
        s.lastAttackRecordedMs = now;
        s.attacks.push(now);
    }

    private void analyze(Player player, PlayerClickState s, long now, Consumer<Violation> sink) {
        if (now - s.lastAnalyzeMs < ANALYZE_COOLDOWN_MS) {
            return;
        }
        s.lastAnalyzeMs = now;

        applyDecay(s, now);
        Settings settings = settings();
        if (s.swings.size() < settings.minSamplesStats) {
            return;
        }

        int cps250  = s.swings.countWithin(250L, now);
        int cps1000 = s.swings.countWithin(1_000L, now);
        int cps3000 = s.swings.countWithin(3_000L, now);
        int attacks1000 = s.attacks.countWithin(1_000L, now);

        IntervalStats stats = s.statsScratch;
        stats.reset();
        stats.collect(s.swings, 3_000L, now, 25L, 450L);

        int score = 0;
        String topSignal = null;

        if (cps1000 >= settings.cpsSustainedHigh) {
            score += 6;
            topSignal = "cps_alto";
        } else if (cps1000 >= settings.cpsSustainedMid) {
            score += 4;
            topSignal = "cps_medio";
        } else if (cps1000 >= settings.cpsSustainedLow) {
            score += 2;
        }

        if (cps1000 < BURST_MIN_SUSTAINED_CPS) {
            // sin senal de rafaga
        } else if (cps250 >= settings.burst250High) {
            score += 8;
            topSignal = "burst_extremo";
        } else if (cps250 >= settings.burst250Low) {
            score += 5;
            topSignal = "burst_alto";
        }

        // A un click por tick o mas rapido (>~17 CPS) el cliente 1.8 procesa uno por tick: el ritmo
        // sale "perfecto" para cualquier humano rapido. La varianza solo significa algo mas lento.
        if (stats.count >= settings.minSamplesStats && stats.mean >= 65.0) {
            if (stats.stddev <= settings.stddevExtremeMs && cps1000 >= settings.minCpsForStats) {
                score += 12;
                topSignal = "ritmo_perfecto";
            } else if (stats.stddev <= settings.stddevRoboticMs && cps1000 >= settings.minCpsForStats) {
                score += 8;
                topSignal = "ritmo_fijo";
            } else if (stats.stddev <= settings.stddevUniformMs
                && cps1000 >= settings.minCpsForStats
                && stats.cv <= settings.cvSuspicious) {
                score += 5;
                topSignal = "ritmo_uniforme";
            }

            if (stats.cv <= settings.cvExtreme && cps1000 >= settings.minCpsForStats) {
                score += 10;
                topSignal = "cv_bajo";
            } else if (stats.cv <= settings.cvSuspicious && cps1000 >= settings.minCpsForStats) {
                score += 6;
            }
            // Sin outliers ni dt multiplo de 50ms: los clientes procesan clicks por tick, es normal en humanos.
        }

        if (cps1000 >= settings.minCpsForStats
            && cps3000 >= settings.minCpsForStats * 2
            && stats.cv <= settings.cvSuspicious
            && !s.swings.hasPauseLongerThan(4_000L, now, settings.humanPauseMs)) {
            score += 4;
            if (topSignal == null) {
                topSignal = "sin_pausas";
            }
        }

        if (cps1000 >= settings.minCpsForStats && attacks1000 == 0 && cps1000 >= settings.airClickMinCps
            && stats.cv <= settings.cvSuspicious) {
            score += 3;
            if (topSignal == null) {
                topSignal = "clics_aire";
            }
        } else if (cps1000 >= settings.minCpsForStats && attacks1000 > 0) {
            double ratio = (double) attacks1000 / (double) cps1000;
            if (ratio >= 0.35 && ratio <= 1.05 && stats.stddev <= settings.stddevRoboticMs) {
                score += 3;
            }
        }

        if (score <= 0) {
            return;
        }

        s.suspicion += score;
        if (s.suspicion < settings.suspicionFlag) {
            return;
        }
        if (now - s.lastFlagMs < settings.flagCooldownMs) {
            return;
        }

        ViolationLevel level = resolveLevel(s.suspicion, score, stats, cps1000, settings);
        String checkName = resolveCheckName(topSignal, stats, settings);
        String details = String.format(Locale.ROOT,
            "score=%.0f cps=%d burst=%d cv=%.2f stddev=%.1fms%s",
            s.suspicion,
            cps1000,
            cps250,
            stats.cv,
            stats.stddev,
            attacks1000 == 0 && cps1000 >= settings.airClickMinCps ? " (aire)" : "");

        sink.accept(new Violation(player, checkName, level, details));
        s.lastFlagMs = now;
        s.suspicion *= 0.45;
    }

    private static ViolationLevel resolveLevel(
        double suspicion,
        int lastScore,
        IntervalStats stats,
        int cps1000,
        Settings s
    ) {
        if (stats.stddev <= s.stddevExtremeMs && cps1000 >= s.minCpsForStats + 4) {
            return ViolationLevel.CRITICAL;
        }
        if (suspicion >= s.suspicionFlag + 18 || lastScore >= 12) {
            return ViolationLevel.HIGH;
        }
        if (suspicion >= s.suspicionFlag + 10 || cps1000 >= s.cpsSustainedHigh) {
            return ViolationLevel.MID;
        }
        return ViolationLevel.LOW;
    }

    private static String resolveCheckName(String topSignal, IntervalStats stats, Settings s) {
        if (topSignal != null) {
            return switch (topSignal) {
                case "ritmo_perfecto", "ritmo_fijo", "cv_bajo", "uniforme", "timer_redondo" -> "autoclicker_variance";
                case "burst_extremo", "burst_alto", "cps_alto", "cps_medio" -> "cps_packet";
                default -> "autoclicker";
            };
        }
        if (stats.stddev <= s.stddevRoboticMs) {
            return "autoclicker_advanced_packet";
        }
        return "autoclicker";
    }

    private void applyDecay(PlayerClickState s, long now) {
        if (s.lastSwingRecordedMs == 0L) {
            return;
        }
        long idle = now - s.lastSwingRecordedMs;
        if (idle > 500L) {
            double factor = Math.pow(0.72, idle / 1000.0);
            s.suspicion *= factor;
        } else if (idle > 250L) {
            s.suspicion = Math.max(0.0, s.suspicion - settings().suspicionDecayPerSec * 0.25);
        }
    }

    private PlayerClickState state(UUID uuid) {
        return states.computeIfAbsent(uuid, k -> new PlayerClickState());
    }

    private AnticheatConfig cfg() {
        return plugin.getAnticheatConfig();
    }

    private boolean isEnabled() {
        AnticheatConfig ac = cfg();
        return ac.isCheckEnabled("autoclicker")
            || ac.isCheckEnabled("cps_packet")
            || ac.isCheckEnabled("autoclicker_advanced");
    }

    private Settings settings() {
        ConfigurationSection sec = cfg().checkSection("autoclicker");
        ConfigurationSection cpsSec = cfg().checkSection("cps_packet");
        ConfigurationSection advSec = cfg().checkSection("autoclicker_advanced");

        Settings s = new Settings();
        s.cpsSustainedLow  = sec != null ? sec.getInt("cps_sustained_low", 20) : 20;
        s.cpsSustainedMid  = sec != null ? sec.getInt("cps_sustained_mid", 24) : 24;
        s.cpsSustainedHigh = sec != null ? sec.getInt("cps_sustained_high", 28) : 28;
        s.burst250Low      = sec != null ? sec.getInt("burst_250_low", 7) : 7;
        s.burst250High     = sec != null ? sec.getInt("burst_250_high", 9) : 9;
        s.minSamplesStats  = sec != null ? sec.getInt("min_samples", 12) : 12;
        s.minCpsForStats   = sec != null ? sec.getInt("variance_min_cps", 12) : 12;
        s.cvSuspicious     = sec != null ? sec.getDouble("cv_suspicious", 0.14) : 0.14;
        s.cvExtreme        = sec != null ? sec.getDouble("cv_extreme", 0.08) : 0.08;
        s.stddevUniformMs  = sec != null ? sec.getDouble("min_stddev_ms", 25.0) : 25.0;
        s.stddevRoboticMs  = advSec != null ? advSec.getDouble("max_stddev_ms", 8.0) : 8.0;
        s.stddevExtremeMs  = advSec != null ? advSec.getDouble("extreme_stddev_ms", 3.0) : 3.0;
        s.outlierRatioMax  = sec != null ? sec.getDouble("outlier_ratio_max", 0.10) : 0.10;
        s.gcdRatioSuspicious = sec != null ? sec.getDouble("gcd_ratio_suspicious", 0.45) : 0.45;
        s.humanPauseMs     = sec != null ? sec.getLong("human_pause_ms", 180L) : 180L;
        s.airClickMinCps   = sec != null ? sec.getInt("air_click_min_cps", 14) : 14;
        s.suspicionFlag    = sec != null ? sec.getInt("suspicion_flag", 14) : 14;
        s.suspicionDecayPerSec = sec != null ? sec.getDouble("suspicion_decay_per_sec", 2.0) : 2.0;
        s.flagCooldownMs   = sec != null ? sec.getLong("flag_cooldown_ms", 2_000L) : 2_000L;

        if (cpsSec != null) {
            long cpsCooldown = cpsSec.getLong("flag_cooldown_ms", 1_500L);
            s.flagCooldownMs = Math.max(s.flagCooldownMs, cpsCooldown);
            int low = cpsSec.getInt("cps_low", 22);
            s.cpsSustainedLow = Math.min(s.cpsSustainedLow, low);
        }
        if (advSec != null) {
            long advCooldown = advSec.getLong("flag_cooldown_ms", 2_000L);
            s.flagCooldownMs = Math.max(s.flagCooldownMs, advCooldown);
            s.minSamplesStats = Math.max(s.minSamplesStats, advSec.getInt("min_samples", 10));
            s.minCpsForStats = Math.max(s.minCpsForStats, advSec.getInt("min_cps", 10));
        }
        return s;
    }

    private static final class PlayerClickState {
        final ClickRingBuffer swings = new ClickRingBuffer(ClickRingBuffer.DEFAULT_CAPACITY);
        final ClickRingBuffer attacks = new ClickRingBuffer(64);
        final IntervalStats statsScratch = new IntervalStats();

        long lastSwingRecordedMs;
        long lastPlaceMs;
        long lastAttackRecordedMs;
        long lastAnalyzeMs;
        long lastFlagMs;
        double suspicion;
    }

    private static final class Settings {
        int cpsSustainedLow;
        int cpsSustainedMid;
        int cpsSustainedHigh;
        int burst250Low;
        int burst250High;
        int minSamplesStats;
        int minCpsForStats;
        double cvSuspicious;
        double cvExtreme;
        double stddevUniformMs;
        double stddevRoboticMs;
        double stddevExtremeMs;
        double outlierRatioMax;
        double gcdRatioSuspicious;
        long humanPauseMs;
        int airClickMinCps;
        int suspicionFlag;
        double suspicionDecayPerSec;
        long flagCooldownMs;
    }

    private static final class IntervalStats {
        int count;
        double mean;
        double stddev;
        double cv;
        double outlierRatio;
        double gcdRatio;

        void reset() {
            count = 0;
            mean = 0.0;
            stddev = 0.0;
            cv = 0.0;
            outlierRatio = 0.0;
            gcdRatio = 0.0;
        }

        void collect(ClickRingBuffer buffer, long windowMs, long now, long minDt, long maxDt) {
            double sum = 0.0;
            double sumSq = 0.0;
            int n = 0;
            int outliers = 0;
            int gcdHits = 0;

            long prev = 0L;
            for (int i = 0; i < buffer.size(); i++) {
                long t = buffer.getFromNewest(i);
                if (now - t > windowMs) {
                    break;
                }
                if (prev != 0L) {
                    long dt = prev - t;
                    if (dt >= minDt && dt <= maxDt) {
                        sum += dt;
                        sumSq += (double) dt * dt;
                        n++;
                        long mod50 = dt % 50L;
                        if (mod50 <= 3L || mod50 >= 47L) {
                            gcdHits++;
                        }
                    }
                }
                prev = t;
            }

            if (n == 0) {
                return;
            }

            mean = sum / n;
            double variance = (sumSq / n) - (mean * mean);
            stddev = Math.sqrt(Math.max(0.0, variance));
            cv = mean > 0.0 ? stddev / mean : 0.0;
            count = n;
            gcdRatio = (double) gcdHits / (double) n;

            prev = 0L;
            for (int i = 0; i < buffer.size(); i++) {
                long t = buffer.getFromNewest(i);
                if (now - t > windowMs) {
                    break;
                }
                if (prev != 0L) {
                    long dt = prev - t;
                    if (dt >= minDt && dt <= maxDt && mean > 0.0 && dt < mean * 0.35) {
                        outliers++;
                    }
                }
                prev = t;
            }
            outlierRatio = (double) outliers / (double) n;
        }
    }
}
