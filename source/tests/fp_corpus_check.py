"""Genera archivos/rutas benignas que históricamente dan FP y los corre por
filter_false_positives + secondary_filter. Reporta cuáles sobreviven como
CRITICAL / SOSPECHOSO (= falso positivo)."""
import os, sys, tempfile
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import main
from fp_filter import filter_false_positives, secondary_filter


class FakeApp:
    legitimate_patterns = None
    _cloud_hash_frequency = {}
    scan_mode = "standard"
    config = {}
    def _apply_remote_fp_rules(self, i): return i
    def _cached_sha256(self, *a, **k): return None
    def _mbaz_check_hash(self, *a, **k): return False
    def _vt_check_hash(self, *a, **k): return None
    def _get_active_launcher_instance_paths(self): return []
    def _get_abandoned_instance_paths(self): return []
    def _filter_by_file_size(self, x): return x
    def _filter_backup_sync(self, x): return x
    def _apply_score_decay(self, x): return x
    def _apply_feedback_thresholds(self, x): return x
    def _apply_human_explanations(self, x): return x
    def _group_related_results(self, x): return x
    def analyze_file_content(self, p): return main.ArgusApp.analyze_file_content(self, p)
    file_analysis_cache = {}
    known_hack_hashes = set()
    def _score_string_hack_likelihood(self, s): return 0.0
    def _apply_process_whitelist(self, x): return main.ArgusApp._apply_process_whitelist(self, x)
    def _apply_process_path_correlation(self, x): return main.ArgusApp._apply_process_path_correlation(self, x)
    def _apply_legit_parent_demote(self, x): return x
    def _apply_authenticode_demote(self, x): return main.ArgusApp._apply_authenticode_demote(self, x)
    def _apply_stale_artifact_demote(self, x): return x
    def _apply_long_uptime_demote(self, x): return x
    def _apply_badlion_informational(self, x): return x
    def _apply_cloud_rarity_and_ban_patterns(self, x): return x
    def _apply_single_indicator_cap(self, x): return main.ArgusApp._apply_single_indicator_cap(self, x)
    def _apply_combination_penalties(self, x): return main.ArgusApp._apply_combination_penalties(self, x)
    def _ai_contextual_boost(self, x): return x


def issue(nombre, ruta, archivo, tipo="file", alerta="SOSPECHOSO", conf=0.6, cat="HACKS", **kw):
    d = dict(nombre=nombre, ruta=ruta, archivo=archivo, tipo=tipo, alerta=alerta,
             confidence=conf, categoria=cat)
    d.update(kw)
    return d


def build_corpus(td):
    """Devuelve lista de (label, issue-dict). Crea archivos reales en td cuando ayuda."""
    def mk(rel, content=b"x"):
        p = os.path.join(td, rel.replace("\\", os.sep))
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, "wb") as f:
            f.write(content)
        return p

    cases = []
    U = r"c:\users\jugador"

    # --- Shaders / graphics (colisión 'vertex', 'reflex') ---
    cases.append(("shader_vertex", issue(
        "shader glsl", rf"{U}\projects\game\shaders",
        rf"{U}\projects\game\shaders\vertex_lighting.glsl")))
    cases.append(("shader_pack_bsl", issue(
        "BSL shader", rf"{U}\appdata\roaming\.minecraft\shaderpacks\BSL",
        rf"{U}\appdata\roaming\.minecraft\shaderpacks\BSL\shaders\gbuffers_terrain.vsh",
        tipo="minecraft_file")))
    cases.append(("nvidia_reflex", issue(
        "NVIDIA Reflex dll", r"c:\program files\nvidia corporation\reflex",
        r"c:\program files\nvidia corporation\reflex\nvreflex.dll", tipo="file")))

    # --- Música (colisión 'pandora', 'remix', 'rise', 'drip') ---
    cases.append(("spotify_data", issue(
        "spotify cache", rf"{U}\appdata\local\spotify\data",
        rf"{U}\appdata\local\spotify\data\ab12.file", tipo="usn_deleted_hack",
        cat="FORENSE", alerta="CRITICAL", conf=0.85, detected_patterns=["usn:file"])))
    cases.append(("music_remix_mp3", issue(
        "cancion", rf"{U}\music\edm",
        rf"{U}\music\edm\Some Artist - Track (Extended Remix).mp3", tipo="file")))
    cases.append(("fl_studio_project", issue(
        "FL project", rf"{U}\documents\image-line\fl studio\projects",
        rf"{U}\documents\image-line\fl studio\projects\drip beat.flp", tipo="file")))
    cases.append(("pandora_saves", issue(
        "pandora game save", rf"{U}\appdata\locallow\supergiant games\pandora",
        rf"{U}\appdata\locallow\supergiant games\pandora\save1.dat", tipo="file")))

    # --- Mods MC legítimos ---
    for mod in ["sodium-fabric-0.5.8.jar", "iris-1.7.0.jar", "create-1.20.1-0.5.1.jar",
                "jei-1.20.1-15.3.0.jar", "ferritecore-6.0.1.jar", "lithium-fabric-0.12.1.jar"]:
        cases.append((f"mod_{mod}", issue(
            f"mod {mod}", rf"{U}\appdata\roaming\.minecraft\mods",
            rf"{U}\appdata\roaming\.minecraft\mods\{mod}", tipo="jar_file", conf=0.55)))

    # --- Launchers ---
    for lc in [("lunarclient", r"appdata\roaming\.lunarclient\offline\1.8\lunar.jar"),
               ("badlion", r"appdata\roaming\badlionclient\bin\bl.jar"),
               ("prism", r"appdata\roaming\prismlauncher\prismlauncher.exe"),
               ("feather", r"appdata\roaming\feather\feather.jar")]:
        cases.append((f"launcher_{lc[0]}", issue(
            f"launcher {lc[0]}", rf"{U}\{os.path.dirname(lc[1])}",
            rf"{U}\{lc[1]}", tipo="jar_file" if lc[1].endswith(".jar") else "file", conf=0.5)))

    # --- Dev / IDE (colisión 'inject', paths) ---
    cases.append(("vscode_ext", issue(
        "vscode extension", rf"{U}\.vscode\extensions\some.ext-1.0",
        rf"{U}\.vscode\extensions\some.ext-1.0\out\inject.js", tipo="file")))
    cases.append(("node_modules", issue(
        "npm pkg", rf"{U}\dev\app\node_modules\reach",
        rf"{U}\dev\app\node_modules\reach\index.js", tipo="file")))
    cases.append(("python_sitepkg", issue(
        "py lib", r"c:\python311\lib\site-packages\numpy",
        r"c:\python311\lib\site-packages\numpy\core\_multiarray.pyd", tipo="file")))

    # --- Herramientas legítimas (procesos) ---
    for pn in ["spotify.exe", "discord.exe", "obs64.exe", "steam.exe", "msedge.exe"]:
        cases.append((f"proc_{pn}", issue(
            f"proceso {pn}", rf"c:\program files\{pn.split('.')[0]}",
            rf"c:\program files\{pn.split('.')[0]}\{pn}", tipo="suspicious_process",
            cat="PROCESO", conf=0.65)))

    # --- osu! / rhythm (colisión 'rise', 'impact', 'insane') ---
    cases.append(("osu_skin", issue(
        "osu skin", rf"{U}\appdata\local\osu!\skins\-  rise  -",
        rf"{U}\appdata\local\osu!\skins\-  rise  -\hit300.png", tipo="file")))
    cases.append(("osu_song", issue(
        "osu beatmap", rf"{U}\appdata\local\osu!\songs\123 artist - insane impact",
        rf"{U}\appdata\local\osu!\songs\123 artist - insane impact\audio.mp3", tipo="file")))

    # --- Garry's Mod addons (nombres genéricos) ---
    cases.append(("gmod_addon", issue(
        "gmod addon", r"c:\program files (x86)\steam\steamapps\common\garrysmod\garrysmod\addons\wiremod",
        r"c:\program files (x86)\steam\steamapps\common\garrysmod\garrysmod\addons\wiremod\lua\autorun\client.lua",
        tipo="file")))

    # --- Ruido forense de apps legítimas ---
    cases.append(("usn_discord_cache", issue(
        "usn discord", rf"{U}\appdata\local\discord\cache",
        rf"{U}\appdata\local\discord\cache\f_00a1b2", tipo="usn_deleted_hack",
        cat="FORENSE", alerta="CRITICAL", conf=0.82, detected_patterns=["usn:deleted"])))
    cases.append(("usn_firefox_cache", issue(
        "usn firefox", rf"{U}\appdata\local\mozilla\firefox\profiles\x.default\cache2\entries",
        rf"{U}\appdata\local\mozilla\firefox\profiles\x.default\cache2\entries\A1B2",
        tipo="usn_deleted_hack", cat="FORENSE", alerta="CRITICAL", conf=0.82)))

    # --- Nombres de clientes legítimos que colisionan ---
    cases.append(("kami_origami_app", issue(
        "origami studio", rf"{U}\appdata\local\programs\origami",
        rf"{U}\appdata\local\programs\origami\origami.exe", tipo="file")))
    cases.append(("lunar_lander_game", issue(
        "juego indie", rf"{U}\games\lunar-lander",
        rf"{U}\games\lunar-lander\lunar.exe", tipo="file")))
    cases.append(("vanish_plugin_note", issue(
        "readme vanish plugin", rf"{U}\servers\smp\plugins",
        rf"{U}\servers\smp\plugins\VanishNoPacket\readme.txt", tipo="file")))

    # --- Más música con nombres de cliente ---
    for track in ["Skrillex - Rise.mp3", "Documentary - The Future.flac",
                  "Meteor Shower - Ambient.wav", "Sigma - Nobody To Love.mp3",
                  "Phobos (Original Mix).mp3", "Impact - Trailer Music.mp3",
                  "Drip Too Hard.mp3", "Flux Pavilion - Bass Cannon.mp3"]:
        cases.append((f"music_{track[:12]}", issue(
            "cancion", rf"{U}\music\library", rf"{U}\music\library\{track}", tipo="file")))

    # --- Juegos con nombres colisionantes ---
    cases.append(("steam_game_meteor", issue(
        "steam game", r"c:\program files (x86)\steam\steamapps\common\Meteor 60 Seconds",
        r"c:\program files (x86)\steam\steamapps\common\Meteor 60 Seconds\meteor.exe", tipo="file")))
    cases.append(("warframe_mod", issue(
        "warframe cache", rf"{U}\appdata\local\warframe\downloaded",
        rf"{U}\appdata\local\warframe\downloaded\Public\Mods.Inertia.bin", tipo="file")))
    cases.append(("valorant_vanguard", issue(
        "riot vanguard", r"c:\program files\riot vanguard",
        r"c:\program files\riot vanguard\vgc.exe", tipo="suspicious_process", cat="PROCESO", conf=0.6)))

    # --- Seguridad / AV ---
    cases.append(("malwarebytes", issue(
        "malwarebytes", r"c:\program files\malwarebytes\anti-malware",
        r"c:\program files\malwarebytes\anti-malware\mbam.exe", tipo="file")))
    cases.append(("system_informer", issue(
        "system informer", r"c:\program files\systeminformer",
        r"c:\program files\systeminformer\systeminformer.exe", tipo="suspicious_process",
        cat="PROCESO", conf=0.7)))

    # --- Streaming / grabación ---
    cases.append(("obs_plugin", issue(
        "obs plugin", r"c:\program files\obs-studio\obs-plugins\64bit",
        r"c:\program files\obs-studio\obs-plugins\64bit\win-capture.dll", tipo="file")))
    cases.append(("streamlabs", issue(
        "streamlabs", rf"{U}\appdata\local\streamlabs\streamlabs desktop",
        rf"{U}\appdata\local\streamlabs\streamlabs desktop\streamlabs obs.exe",
        tipo="suspicious_process", cat="PROCESO", conf=0.6)))

    # --- BetterDiscord / plugins de apps ---
    cases.append(("betterdiscord", issue(
        "betterdiscord plugin", rf"{U}\appdata\roaming\betterdiscord\plugins",
        rf"{U}\appdata\roaming\betterdiscord\plugins\SomePlugin.plugin.js", tipo="file")))

    # --- AHK legítimo (NO autoclick) ---
    cases.append(("ahk_text_expander", issue(
        "ahk script", rf"{U}\documents\autohotkey",
        rf"{U}\documents\autohotkey\text_expander.ahk",
        tipo="file", detected_patterns=[])))

    # --- Configs de MC con keywords ('reach', 'velocity', 'sprint') ---
    cases.append(("mc_keybinds_cfg", issue(
        "options.txt", rf"{U}\appdata\roaming\.minecraft",
        rf"{U}\appdata\roaming\.minecraft\options.txt", tipo="minecraft_file",
        detected_patterns=[])))
    cases.append(("sodium_config", issue(
        "sodium config", rf"{U}\appdata\roaming\.minecraft\config",
        rf"{U}\appdata\roaming\.minecraft\config\sodium-options.json", tipo="file")))

    # --- Resource pack legítimo (Faithful) ---
    cases.append(("resourcepack_faithful", issue(
        "faithful pack", rf"{U}\appdata\roaming\.minecraft\resourcepacks",
        rf"{U}\appdata\roaming\.minecraft\resourcepacks\Faithful 32x.zip",
        tipo="minecraft_file", conf=0.5)))

    # --- Wallpaper Engine ---
    cases.append(("wallpaper_engine", issue(
        "wallpaper engine", r"c:\program files (x86)\steam\steamapps\common\wallpaper_engine",
        r"c:\program files (x86)\steam\steamapps\common\wallpaper_engine\wallpaper32.exe",
        tipo="suspicious_process", cat="PROCESO", conf=0.6)))

    # --- Modrinth / otros launchers ---
    cases.append(("modrinth_app", issue(
        "modrinth", rf"{U}\appdata\roaming\com.modrinth.theseus",
        rf"{U}\appdata\roaming\com.modrinth.theseus\profiles\fabric\mods\sodium.jar",
        tipo="jar_file", conf=0.5)))

    # =========================================================================
    #  MUST-DETECT — cheats reales / complementos prohibidos: DEBEN sobrevivir
    # =========================================================================
    md = []
    def must(label, iss):
        md.append((f"[DETECT]{label}", iss))
    MC = rf"{U}\appdata\roaming\.minecraft\mods"
    must("vape_exe", issue("vape", rf"{U}\downloads", rf"{U}\downloads\Vape V4.exe",
                           tipo="file", alerta="CRITICAL", conf=0.9))
    must("liquidbounce_jar", issue("lb", MC, rf"{MC}\LiquidBounce-b90.jar", tipo="jar_file", conf=0.7))
    must("wurst_jar", issue("wurst", MC, rf"{MC}\Wurst-Client-v7.jar", tipo="jar_file", conf=0.7))
    must("meteor_jar", issue("meteor", MC, rf"{MC}\meteor-client-0.5.8.jar", tipo="jar_file", conf=0.7))
    must("sigma5_jar", issue("sigma", MC, rf"{MC}\sigma5.jar", tipo="jar_file", conf=0.7))
    must("slinky_dll", issue("slinky", rf"{U}\downloads", rf"{U}\downloads\slinky.dll",
                             tipo="file", alerta="CRITICAL", conf=0.85))
    must("baritone_jar", issue("baritone", MC, rf"{MC}\baritone-api-1.10.1.jar", tipo="jar_file", conf=0.7))
    must("weave_loader", issue("weave", rf"{U}\.weave", rf"{U}\.weave\weave-loader.jar",
                               tipo="jar_file", conf=0.7))
    must("autoclicker_exe", issue("autoclicker", rf"{U}\downloads",
                                  rf"{U}\downloads\Free Auto Clicker.exe", tipo="file", conf=0.7))
    must("killaura_class", issue("killaura module", MC,
                                 rf"{MC}\dump\me\client\module\KillAura.class", tipo="file", conf=0.7))
    must("xray_pack", issue("xray pack", rf"{U}\appdata\roaming\.minecraft\resourcepacks",
                            rf"{U}\appdata\roaming\.minecraft\resourcepacks\XRay-Ultimate.zip",
                            tipo="minecraft_file", conf=0.6))
    must("entropy_client", issue("entropy", rf"{U}\downloads", rf"{U}\downloads\EntropyClient.jar",
                                 tipo="jar_file", conf=0.7))
    must("vape_inject_camouflaged", issue("spotify?", rf"{U}\appdata\roaming\spotify",
                                          rf"{U}\appdata\roaming\spotify\vape_inject.exe",
                                          tipo="file", conf=0.7))
    must("fullbright_pack", issue("fullbright", rf"{U}\appdata\roaming\.minecraft\resourcepacks",
                                  rf"{U}\appdata\roaming\.minecraft\resourcepacks\FullBright+NoDarkness.zip",
                                  tipo="minecraft_file", conf=0.6))
    must("killaura_camouflaged_discord", issue("discord?", rf"{U}\appdata\local\discord\app-1.0",
                                               rf"{U}\appdata\local\discord\app-1.0\KillAura.dll",
                                               tipo="file", conf=0.6))

    return cases + md


def run():
    import io, contextlib
    fps, misses = [], []
    with tempfile.TemporaryDirectory() as td:
        app = FakeApp()
        corpus = build_corpus(td)
        for label, iss in corpus:
            is_detect = label.startswith("[DETECT]")
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    o2 = secondary_filter(app, filter_false_positives(app, [dict(iss)]))
            except Exception as e:
                print(f"  ERR {label}: {e}")
                continue
            survived = any((o.get("alerta") or "").upper() in
                           ("CRITICAL", "SOSPECHOSO", "MUY_SOSPECHOSO", "POCO_SOSPECHOSO")
                           for o in o2)
            if is_detect and not survived:
                misses.append(label)
            elif not is_detect and survived:
                top = o2[0] if o2 else {}
                fps.append((label, (top.get("alerta") or "").upper(), top.get("tipo"),
                            top.get("ai_score"), top.get("detected_patterns")))
    benign = sum(1 for l, _ in build_corpus(tempfile.mkdtemp()) if not l.startswith("[DETECT]"))
    ndet = sum(1 for l, _ in build_corpus(tempfile.mkdtemp()) if l.startswith("[DETECT]"))
    print(f"\n{'='*72}")
    print(f"FALSOS POSITIVOS: {len(fps)} / {benign} benignos")
    for s in fps:
        print(f"  [FP {s[1]:9}] {s[0]:28} tipo={s[2]} score={s[3]} pats={s[4]}")
    print(f"\nCHEATS NO DETECTADOS (miss): {len(misses)} / {ndet}")
    for m in misses:
        print(f"  [MISS] {m}")
    print('='*72)
    return fps, misses


if __name__ == "__main__":
    fps, misses = run()
    raise SystemExit(1 if (fps or misses) else 0)
