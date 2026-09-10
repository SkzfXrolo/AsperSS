"""
ScanPipeline — fases nombradas, modos Fast/Standard/Paranoid, cancelación y ETA.
v1.8 mega-update. Orquesta métodos existentes de ArgusApp sin duplicar detección.
"""
from __future__ import annotations

import concurrent.futures
import os
import time
from typing import Any, Callable, Dict, List, Optional, Sequence


# Modos de producto (plan mega-update)
MODE_FAST = "fast"
MODE_STANDARD = "standard"
MODE_PARANOID = "paranoid"

MODE_ALIASES = {
    "quick": MODE_FAST,
    "lite": MODE_FAST,
    "full": MODE_STANDARD,
    "normal": MODE_STANDARD,
    "deep": MODE_PARANOID,
    "paranoid": MODE_PARANOID,
    "fast": MODE_FAST,
    "standard": MODE_STANDARD,
}


# ETA objetivo en segundos (plan)
ETA_SEC = {
    MODE_FAST: 260,       # ~4.5 min (deep_proc light + remote/VAC/MRU)
    MODE_STANDARD: 900,   # ~15 min (persistencia/forense cableados)
    MODE_PARANOID: 1800,  # ~30 min (event logs + signed tamper)
}


# Fases canónicas. Cada fase es un id estable; el runner las mapea a callables.
PHASE_CATALOG: Dict[str, str] = {
    "processes": "Procesos + javaagent/JDWP/Weave",
    "autoclickers": "Autoclickers + macros HID/AHK",
    "jars_mc": "JARs / archivos Minecraft",
    "prefetch_bam": "Prefetch + BAM",
    "temp_recent": "Temp / Recent / UserAssist / JumpLists",
    "integrity": "Integridad anti-bypass",
    "high_value": "P1 ghost configs/registry/recycle/startup",
    "complements": "Baritone / Litematica / OptiFine / Xray / webhooks",
    "registry_exec": "Amcache / ShimCache / SRUM / Run",
    "usn_killchain": "USN Journal + Kill Chain",
    "forensics_pack": "Pack forense / novel surfaces",
    "browser": "Descargas / historial browser cheats",
    "deep_proc": "Path/uptime procesos + cloud hash + tree",
    "memory_strings": "Strings en memoria / JARs cargados",
    "yara_java": "YARA sobre JARs / procesos Java",
    "mouse_session": "Sesión mouse / weight",
    "evasion": "VPN / hosts / DNS / evasión pre-SS",
    "filter_verdict": "Filtro FP + veredicto SS",
}


# Subsets por modo
MODE_PHASES: Dict[str, List[str]] = {
    MODE_FAST: [
        "processes",
        "autoclickers",
        "jars_mc",
        "prefetch_bam",
        "temp_recent",
        "complements",
        "integrity",
        "high_value",
        "deep_proc",
        "evasion",
        "filter_verdict",
    ],
    MODE_STANDARD: [
        "processes",
        "autoclickers",
        "jars_mc",
        "prefetch_bam",
        "temp_recent",
        "complements",
        "integrity",
        "high_value",
        "deep_proc",
        "registry_exec",
        "usn_killchain",
        "forensics_pack",
        "browser",
        "memory_strings",
        "evasion",
        "filter_verdict",
    ],
    MODE_PARANOID: [
        "processes",
        "autoclickers",
        "jars_mc",
        "prefetch_bam",
        "temp_recent",
        "complements",
        "integrity",
        "high_value",
        "deep_proc",
        "registry_exec",
        "usn_killchain",
        "forensics_pack",
        "browser",
        "memory_strings",
        "yara_java",
        "mouse_session",
        "evasion",
        "filter_verdict",
    ],
}


def normalize_mode(name: Optional[str]) -> str:
    if not name:
        return MODE_STANDARD
    key = str(name).strip().lower()
    return MODE_ALIASES.get(key, MODE_STANDARD if key not in MODE_PHASES else key)


def phases_for_mode(mode: str) -> List[str]:
    mode = normalize_mode(mode)
    return list(MODE_PHASES.get(mode, MODE_PHASES[MODE_STANDARD]))


def eta_for_mode(mode: str) -> int:
    return int(ETA_SEC.get(normalize_mode(mode), ETA_SEC[MODE_STANDARD]))


class ScanPipeline:
    """Ejecuta fases en orden; respeta cancelación vía app._scan_cancelled()."""

    def __init__(
        self,
        app: Any,
        mode: str = MODE_STANDARD,
        progress_cb: Optional[Callable[[str, float], None]] = None,
    ):
        self.app = app
        self.mode = normalize_mode(mode)
        self.phases = phases_for_mode(self.mode)
        self.progress_cb = progress_cb
        self.started_at = 0.0
        self.phase_timings: Dict[str, float] = {}
        self._handlers = self._bind_handlers()

    def _bind_handlers(self) -> Dict[str, Callable[[], None]]:
        app = self.app
        return {
            "processes": lambda: self._call_many(
                "scan_processes_logic",
                "scan_background_processes",
                "advanced_minecraft_process_analysis",
                "scan_javaagent_args",
                "scan_jdwp_port",
                "scan_weave_loader",
                "scan_bat_ps1_launchers",
                "scan_dll_injection_java",
                "scan_active_injectors",
                "scan_running_processes",
                "scan_java_parent_process",
            ),
            "autoclickers": lambda: self._call_many(
                "scan_autoclick_tools",
                "scan_bloody_a4tech",
                "scan_arduino_hid",
                "scan_steelseries_corsair",
                "scan_logitech_macros",
                "scan_razer_macros",
                "scan_ahk_scripts",
            ),
            "jars_mc": lambda: self._call_many(
                "scan_minecraft_files_logic",
                "scan_all_jars",
                "scan_modified_minecraft_jar",
                "scan_minecraft_mods_blacklist",
                "scan_minecraft_jar_hash",
                "scan_common_hack_locations",
                "scan_exe_entropy_and_packing",
                "scan_config_tfidf",
                "scan_hack_properties_configs",
            ),
            "deep_proc": lambda: self._run_deep_proc(),
            "prefetch_bam": lambda: self._call_many(
                "scan_prefetch_hacks",
                "scan_prefetch_execution_parser",
                "scan_prefetch_referenced_files",
                "scan_bam_registry",
                "scan_prefetch_jna",
            ),
            "temp_recent": lambda: self._call_many(
                "scan_recent_files",
                "scan_downloads_folder",
                "scan_temp_jna",
                "scan_temp_jars",
                "scan_executed_userassist",
                "scan_jump_lists",
            ),
            "complements": lambda: self._call_many(
                "scan_baritone_config",
                "scan_schematica_litematica",
                "scan_optifine_zoom",
                "scan_xray_resourcepacks",
                "scan_discord_webhooks",
                "scan_options_txt_keybinds",
                "scan_f3t_log_exploit",
            ),
            "integrity": lambda: self._run_integrity(),
            "high_value": lambda: self._run_high_value(),
            "registry_exec": lambda: self._call_many(
                "scan_amcache",
                "scan_appcompat_shimcache",
                "scan_srum_artifacts",
                "scan_registry_run_persistence",
            ),
            "usn_killchain": lambda: self._call_many(
                "scan_usn_minecraft_jars",
                "scan_kill_chain",
            ),
            "forensics_pack": lambda: self._run_pack(),
            "browser": lambda: self._call_many(
                "scan_browser_downloads",
                "scan_browser_history_cheats",
                "scan_browser_history_sites",
                "scan_browser_hack_cookies",
            ),
            "memory_strings": lambda: self._call("scan_process_memory_strings"),
            "yara_java": lambda: self._run_yara(),
            "mouse_session": lambda: self._run_mouse(),
            "evasion": lambda: self._run_evasion(),
            "filter_verdict": lambda: self._run_filter_verdict(),
        }

    def _cancelled(self) -> bool:
        try:
            return bool(self.app._scan_cancelled())
        except Exception:
            return False

    def _scanner_timeout_sec(self) -> float:
        """P1 #117 — timeout por scanner (override ARGUS_SCANNER_TIMEOUT)."""
        try:
            env = os.environ.get("ARGUS_SCANNER_TIMEOUT")
            if env:
                return float(env)
        except Exception:
            pass
        return {MODE_FAST: 12.0, MODE_STANDARD: 15.0, MODE_PARANOID: 40.0}.get(
            self.mode, 15.0
        )

    def _call(self, method_name: str) -> None:
        fn = getattr(self.app, method_name, None)
        if not callable(fn):
            print(f"[pipeline] skip missing: {method_name}")
            return
        timeout = self._scanner_timeout_sec()
        t0 = time.time()
        try:
            # Timeout en hilo: evita que un scanner trabado congela todo el pipeline
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                fut = ex.submit(fn)
                try:
                    result = fut.result(timeout=timeout)
                except concurrent.futures.TimeoutError:
                    print(f"[pipeline] WARN timeout {timeout:.0f}s: {method_name}")
                    try:
                        fut.cancel()
                    except Exception:
                        pass
                    return
            if isinstance(result, list) and result:
                issues = getattr(self.app, "issues_found", None)
                if isinstance(issues, list):
                    issues.extend(result)
            elapsed = time.time() - t0
            if elapsed > timeout * 0.8:
                print(f"[pipeline] slow {method_name}: {elapsed:.1f}s")
        except Exception as e:
            print(f"[pipeline] {method_name} error: {e}")

    def _call_many(self, *names: str) -> None:
        for n in names:
            if self._cancelled():
                return
            self._call(n)

    def _call_many_parallel(self, *names: str, max_workers: int = 3) -> None:
        """P1 #111 — ejecuta scanners independientes en paralelo (con timeout c/u)."""
        if self._cancelled():
            return
        timeout = self._scanner_timeout_sec()
        names = [n for n in names if callable(getattr(self.app, n, None))]
        if not names:
            return
        workers = max(1, min(max_workers, len(names)))

        def _run_one(method_name: str):
            if self._cancelled():
                return method_name, "cancelled", None
            fn = getattr(self.app, method_name)
            t0 = time.time()
            try:
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
                    fut = ex.submit(fn)
                    try:
                        result = fut.result(timeout=timeout)
                    except concurrent.futures.TimeoutError:
                        return method_name, "timeout", None
                return method_name, "ok", result
            except Exception as e:
                return method_name, f"error:{e}", None
            finally:
                _ = time.time() - t0

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
            futs = [pool.submit(_run_one, n) for n in names]
            for fut in concurrent.futures.as_completed(futs):
                if self._cancelled():
                    break
                try:
                    name, status, result = fut.result()
                except Exception as e:
                    print(f"[pipeline/parallel] worker error: {e}")
                    continue
                if status == "timeout":
                    print(f"[pipeline] WARN timeout {timeout:.0f}s: {name}")
                elif status.startswith("error:"):
                    print(f"[pipeline] {name} {status}")
                elif isinstance(result, list) and result:
                    issues = getattr(self.app, "issues_found", None)
                    if isinstance(issues, list):
                        issues.extend(result)

    def _run_integrity(self) -> None:
        try:
            from ss_integrity import scan_integrity
            findings = scan_integrity(self.app) or []
            if findings:
                self.app.issues_found.extend(findings)
                print(f"[pipeline/integrity] {len(findings)} señal(es)")
        except Exception as e:
            print(f"[pipeline/integrity] {e}")

    def _run_high_value(self) -> None:
        # Ghost configs viven en main — deben correr en Fast/Standard (Weave ya en processes)
        self._call("scan_ghost_client_configs")
        try:
            from scan_modules.high_value_checks import run_high_value_checks
            findings = run_high_value_checks(self.app) or []
            if findings:
                self.app.issues_found.extend(findings)
                print(f"[pipeline/high_value] {len(findings)} hallazgo(s)")
        except Exception as e:
            print(f"[pipeline/high_value] {e}")
        try:
            from scan_modules.jar_structure import scan_mods_jar_structure
            js = scan_mods_jar_structure(self.app) or []
            if js:
                self.app.issues_found.extend(js)
                print(f"[pipeline/jar_structure] {len(js)} JAR(s) sin metadata mod")
        except Exception as e:
            print(f"[pipeline/jar_structure] {e}")

    def _run_evasion(self) -> None:
        """VPN/hosts/DNS primero (alimentan score), luego indicadores agregados."""
        self._call_many(
            "scan_av_interference",
            "scan_vpn_adapters",
            "scan_hosts_file",
            "scan_dns_cache",
            "scan_defender_exclusions",
            "scan_time_drift_forensics",
            "scan_evasion_indicators",
        )

    def _run_deep_proc(self) -> None:
        """Procesos/red/superficies: subset ligero en Fast, full en Standard+."""
        light = [
            "scan_process_path_correlation",
            "scan_multiple_javaw",
            "scan_minecraft_safe_mode",
            "scan_self_deletion_hacks",
            "scan_clipboard_content",
            "scan_exact_hack_names",
            "scan_windowless_java",
            "scan_cheat_engine",
            "scan_temp_dlls",
            "scan_deleted_recycle",
            "scan_jitter_scripts",
            "scan_cmd_history_full",
            "scan_remote_access_tools",
            "scan_minecraft_lock_files",
            "scan_run_mru",
            "scan_virtual_audio_cable",
        ]
        heavy = [
            "scan_process_hashes_cloud",
            "scan_process_tree",
            "scan_prescan_disk_activity",
            "scan_startup_entries",
            "scan_inetcache",
            "scan_suspicious_folders",
            "scan_java_policy",
            "scan_minecraft_fs_changes",
            "scan_folder_name_nlp",
            "scan_readonly_suspicious_files",
            "scan_installed_programs",
            "scan_java_suspicious_tls",
            "scan_javaw_network_connections",
            "scan_packet_sniffers",
            "scan_java_dll_nonstandard",
            "scan_injected_threads",
            "scan_minecraft_accounts",
            "scan_java_rwx_memory",
            "scan_input_hook_processes",
            "scan_powershell_history",
            "scan_discord_local_settings",
            "scan_discord_cache",
            "scan_messaging_downloads",
            "scan_minecraft_crash_reports",
            "scan_hack_fingerprints",
            "scan_options_resolution_mismatch",
            "scan_dll_sideloading",
            "scan_thumbcache_artifacts",
            "scan_lunar_unofficial_modules",
            "scan_peb_unlink_mismatch",
            "scan_wmi_event_subscriptions",
            "scan_suspicious_kernel_drivers",
            "scan_securityhealth_disable_events",
            "scan_nbt_exploits_saves",
            "scan_player_baseline_delta",
            "scan_process_crosscheck",
            "scan_ghost_client_registry",
            "scan_usb_devices",
            "scan_network_connections",
            "scan_services",
            "scan_wsl_bash_history",
            # Persistencia / LOLBins / forense (antes solo legacy)
            "scan_scheduled_tasks",
            "scan_scheduled_tasks_suspicious_args",
            "scan_com_hijacking_registry",
            "scan_python_hack_scripts",
            "scan_exploit_tools",
            "scan_ddos_applications",
            "scan_browser_extensions_suspicious",
            "scan_recent_firewall_rules",
            "scan_defender_quarantine",
            "scan_typed_paths",
            "scan_usb_history",
            "scan_muicache",
            "scan_pca_telemetry",
            "scan_recent_msi_installs",
            "scan_recent_install_tasks",
            "scan_recent_lnk",
            "scan_recent_files_lnk",
            "scan_windows_search_history",
            "scan_dns_cache_recent",
            # scan_amcache_unique_sha1 omitido: solapa con scan_amcache (mismo hive)
            "scan_appcompatflags_store",
            "scan_texture_packs",
            "scan_jdk_installed",
            "scan_minecraft_install_date",
            "scan_minecraft_last_session",
            "scan_minecraft_version_count",
            "scan_git_repos_desktop",
            "scan_backup_sync_locations",
            "scan_ip_forwarding",
            "scan_crash_dumps",
            "scan_shadow_copy_artifacts",
            "scan_deleted_mass_event",
            "scan_wifi_promiscuous_mode",
            "scan_java_process_parent",
            "scan_recent_docs_registry",
        ]
        # Event logs / firmas críticas: caros → solo Paranoid
        paranoid_extra = [
            "scan_sysmon_operational",
            "scan_security_4688_events",
            "scan_lolbins_extra",
            "scan_defender_asr_events",
            "scan_system_signed_tamper",
            "scan_firmware_uefi_indicators",
            "scan_office_mru_registry",
        ]
        # Light + heavy: paralelo. Son todos de lectura (winreg read-only es
        # thread-safe; el resto es subprocess/fs/psutil). `_read_usn_journal`
        # tiene lock propio para no lanzar fsutil dos veces bajo paralelismo.
        # paranoid_extra queda secuencial: son consultas pesadas al Event Log
        # de Security y correrlas juntas lo satura.
        workers = {MODE_FAST: 2, MODE_STANDARD: 3, MODE_PARANOID: 4}.get(self.mode, 3)
        self._call_many_parallel(*light, max_workers=workers)
        if self.mode != MODE_FAST:
            self._call_many_parallel(*heavy, max_workers=workers)
        if self.mode == MODE_PARANOID:
            self._call_many(*paranoid_extra)

    def _run_pack(self) -> None:
        try:
            from scan_modules.executor import run_pack_modules
            issues = run_pack_modules(self.app, progress_cb=lambda t: self._progress(t, None))
            if issues:
                self.app.issues_found.extend(issues)
        except Exception as e:
            print(f"[pipeline/pack] {e}")

    def _run_yara(self) -> None:
        try:
            from scan_modules.yara_java import scan_java_yara
            findings = scan_java_yara(self.app) or []
            if findings:
                self.app.issues_found.extend(findings)
                print(f"[pipeline/yara] {len(findings)} match(es)")
        except Exception as e:
            print(f"[pipeline/yara] {e}")

    def _run_mouse(self) -> None:
        det = getattr(self.app, "mouse_detector", None)
        if not det:
            return
        try:
            det.stop_monitoring()
            session = det.get_session_findings() or []
            if session:
                mf = getattr(self.app, "mouse_findings", None)
                if isinstance(mf, list):
                    mf.extend(session)
                else:
                    self.app.mouse_findings = list(session)
                self.app.issues_found.extend(session)
        except Exception as e:
            print(f"[pipeline/mouse] {e}")

    def _run_filter_verdict(self) -> None:
        app = self.app
        try:
            if getattr(app, "forensic_findings", None):
                app.issues_found.extend(app.forensic_findings or [])
        except Exception:
            pass
        try:
            if getattr(app, "mouse_findings", None):
                # already may be merged; keep idempotent-ish
                pass
        except Exception:
            pass
        try:
            from fp_filter import filter_false_positives, secondary_filter
            app.issues_found = filter_false_positives(app, app.issues_found)
            app.issues_found = secondary_filter(app, app.issues_found)
        except Exception:
            try:
                app.issues_found = app.filter_false_positives(app.issues_found)
                app.issues_found = app.secondary_filter(app.issues_found)
            except Exception as e:
                print(f"[pipeline/filter] {e}")
        try:
            if hasattr(app, "_apply_temporal_correlation"):
                app.issues_found = app._apply_temporal_correlation(app.issues_found)
        except Exception:
            pass
        try:
            if hasattr(app, "_apply_forensic_kill_chain"):
                app.issues_found = app._apply_forensic_kill_chain(app.issues_found)
        except Exception as e:
            print(f"[pipeline/kill_chain] {e}")
        # Enriquecer evidencia staff (hash/timestamp/related) antes del veredicto
        try:
            from issue_enrichment import enrich_issues
            app.issues_found = enrich_issues(app.issues_found, app=app)
        except Exception as e:
            print(f"[pipeline/enrich] {e}")
        try:
            from ss_verdict import build_verdict, verdict_issue
            app.ss_verdict = build_verdict(
                app.issues_found,
                getattr(app, "mouse_findings", None),
            )
            # Top 5 hallazgos para VerdictCard / Discord
            try:
                ranked = sorted(
                    [i for i in app.issues_found if (i.get("tipo") or "") != "ss_verdict"],
                    key=lambda x: (
                        {"CRITICAL": 3, "SOSPECHOSO": 2, "POCO_SOSPECHOSO": 1}.get(
                            (x.get("alerta") or "").upper(), 0
                        ),
                        float(x.get("confidence") or 0)
                        if float(x.get("confidence") or 0) <= 1
                        else float(x.get("confidence") or 0) / 100.0,
                    ),
                    reverse=True,
                )
                app.ss_verdict["top_findings"] = [
                    {
                        "nombre": i.get("nombre"),
                        "tipo": i.get("tipo"),
                        "alerta": i.get("alerta"),
                        "timestamp": i.get("timestamp") or i.get("last_executed") or "",
                        "file_hash": (i.get("file_hash") or i.get("sha256") or "")[:16],
                        "related_count": (i.get("extra") or {}).get("related_count", 0),
                        "combination_penalty": i.get("combination_penalty")
                        or (i.get("extra") or {}).get("combination_penalty")
                        or "",
                    }
                    for i in ranked[:5]
                ]
            except Exception:
                app.ss_verdict["top_findings"] = []
            vi = verdict_issue(app.ss_verdict)
            app.issues_found.insert(0, vi)
            # Timings de fase para staff
            try:
                timings = getattr(self, "phase_timings", None) or {}
                if timings:
                    app.pipeline_timings = dict(timings)
                    bits = [f"{k}:{v:.1f}s" for k, v in list(timings.items())[:8]]
                    print(f"[pipeline/perf] {' | '.join(bits)}")
            except Exception:
                pass
            print(
                f"[pipeline/verdict] {app.ss_verdict.get('verdict')} "
                f"risk={app.ss_verdict.get('risk_score')}/100"
            )
        except Exception as e:
            print(f"[pipeline/verdict] {e}")

    def _progress(self, label: str, frac: Optional[float]) -> None:
        if self.progress_cb:
            try:
                self.progress_cb(label, frac if frac is not None else 0.0)
            except Exception:
                pass
        try:
            if hasattr(self.app, "_set_scan_phase"):
                self.app._set_scan_phase(label)
        except Exception:
            pass

    def run(self) -> Dict[str, Any]:
        self.started_at = time.time()
        total = max(1, len(self.phases))
        print(f"[pipeline] mode={self.mode} phases={total} eta~{eta_for_mode(self.mode)}s")
        for i, phase_id in enumerate(self.phases):
            if self._cancelled():
                print("[pipeline] cancelled")
                break
            label = PHASE_CATALOG.get(phase_id, phase_id)
            frac = i / total
            self._progress(f"{label} ({self.mode})", frac)
            t0 = time.time()
            handler = self._handlers.get(phase_id)
            if handler:
                try:
                    handler()
                except Exception as e:
                    print(f"[pipeline] phase {phase_id} failed: {e}")
            self.phase_timings[phase_id] = time.time() - t0
            print(f"[pipeline] {phase_id}: {self.phase_timings[phase_id]:.2f}s")
        elapsed = time.time() - self.started_at
        self._progress("Scan pipeline completo", 1.0)
        return {
            "mode": self.mode,
            "elapsed_sec": elapsed,
            "eta_sec": eta_for_mode(self.mode),
            "phases": list(self.phases),
            "timings": dict(self.phase_timings),
        }


def profile_dict(mode: str) -> dict:
    """Compat con config.profiles.get_profile."""
    mode = normalize_mode(mode)
    threads = {MODE_FAST: 2, MODE_STANDARD: 4, MODE_PARANOID: 6}[mode]
    timeout = {MODE_FAST: 8, MODE_STANDARD: 15, MODE_PARANOID: 40}[mode]
    return {
        "name": mode,
        "threads": threads,
        "timeout_sec": timeout,
        "eta_sec": eta_for_mode(mode),
        "phases": phases_for_mode(mode),
    }
