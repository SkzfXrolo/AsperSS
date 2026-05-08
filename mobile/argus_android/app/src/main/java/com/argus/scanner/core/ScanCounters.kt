package com.argus.scanner.core

import java.util.concurrent.atomic.AtomicLong

/**
 * ScanCounters — contadores compartidos para reportar `total_files_scanned`
 * y `total_dirs_scanned` al backend Argus, mismo contrato que los scanners
 * Windows / Linux.
 *
 * Antes de Pack 27 (post v1.6.49-android3), los scans de Android llegaban
 * al panel staff con "0 archivos escaneados" porque el contrato del
 * `POST /api/scans/<id>/results` espera estos dos campos y la APK no los
 * enviaba. Esto hacía que los scans móviles parecieran vacíos en
 * `panel.html` ("Archivos escaneados: 0") aunque internamente se
 * recorrieran cientos de archivos.
 *
 * Cada scanner que recorra archivos del filesystem (FileScanner,
 * LauncherScanner, MemoryEditorScanner, FileObserverScanner) recibe una
 * instancia y la incrementa cada vez que toca un File / Directory.
 * Atomic porque FileObserverScanner corre en paralelo con los demás.
 */
class ScanCounters(
    val files: AtomicLong = AtomicLong(0),
    val dirs:  AtomicLong = AtomicLong(0),
) {
    fun incFile()           { files.incrementAndGet() }
    fun addFiles(n: Long)   { if (n > 0) files.addAndGet(n) }
    fun incDir()            { dirs.incrementAndGet() }
    fun addDirs(n: Long)    { if (n > 0) dirs.addAndGet(n) }

    val filesCount: Long get() = files.get()
    val dirsCount:  Long get() = dirs.get()
}
