package com.argusprojects.argusmc.anticheat;

/**
 * Marker interface para checks del anti-cheat. No define metodos
 * porque cada check se registra como Listener de eventos Bukkit
 * concretos (PlayerMoveEvent, EntityDamageByEntityEvent, etc.) y
 * llama a {@link ViolationManager#flag(Violation)} cuando detecta
 * comportamiento sospechoso.
 *
 * <p>Existe la interfaz solo para que el manager pueda iterar sobre
 * la lista de checks y exponer su estado (enabled/disabled).
 */
public interface Check {
    String name();
    boolean isEnabled();
}
