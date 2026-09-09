"""Minuto de partido "de reloj", calculado desde los Hitos — fuente única
para el servidor (modo-vivo-sustituciones-cierre-plan.md, Área 3, T3/T22).

Antes de esto, el minuto de un evento en vivo era 100% lo que el cliente
mandaba (`CargaEvento` en `MesaPanel.tsx` pedía un `<input type="number">` a
mano) — un dato tan confiable como quisiera hacerlo el dispositivo que lo
mandó (Sección 3 del plan, hallazgo de seguridad: "minuto falsificable por
el cliente"). Esta función es la misma cuenta que ya hace
`Cronometro.tsx::calcularElapsedMs` del lado del cliente (para que el
reloj que el operador VE sea consistente con el que el servidor usa), pero
recorriendo TODOS los períodos ya cerrados además del segmento abierto —
`calcularElapsedMs` solo necesita el segmento abierto porque es lo único
que el cronómetro muestra en pantalla; acá hace falta el minuto ACUMULADO
del partido completo (67' de un gol en el 2do tiempo, no "22' de este
período"), que es la convención real de "minuto de gol" en cualquier
planilla.
"""
from datetime import datetime

from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.hito_partido import HitoPartido


def _ms_corriendo(inicio: datetime, fin: datetime, pausas: list[HitoPartido]) -> float:
    """Milisegundos efectivamente corridos entre `inicio` y `fin`, restando
    cualquier tramo en Pausa dentro de esa ventana — mismo algoritmo que
    `calcularElapsedMs` (Cronometro.tsx), generalizado a un segmento
    arbitrario en vez de "desde el inicio del período hasta ahora"."""
    relevantes = sorted(
        (h for h in pausas if inicio <= h.timestamp_real <= fin),
        key=lambda h: h.timestamp_real,
    )
    running_since: datetime | None = inicio
    acumulado = 0.0
    for h in relevantes:
        if h.tipo_hito == "Pausa":
            if running_since is not None:
                acumulado += (h.timestamp_real - running_since).total_seconds() * 1000
                running_since = None
        elif running_since is None:
            running_since = h.timestamp_real
    if running_since is not None:
        acumulado += max(0.0, (fin - running_since).total_seconds() * 1000)
    return acumulado


def calcular_minuto_actual(
    hitos: list[HitoPartido], config: ConfiguracionTiempoTorneo, ahora: datetime
) -> int | None:
    """Minuto acumulado del partido en este instante.

    Devuelve el ÚLTIMO valor conocido incluso en pausa o entretiempo — un
    evento cargado ahí es legítimo (Sección 1 del plan, dataflow de "evento
    en vivo": "tarjeta a quien discute en el entretiempo" no debe
    bloquearse ni perder el minuto). `None` solo si el partido ni siquiera
    tiene `Inicio_Partido` todavía — ahí no hay ningún minuto que capturar.
    """
    inicio_partido = next((h for h in hitos if h.tipo_hito == "Inicio_Partido"), None)
    if inicio_partido is None:
        return None

    segmentos: list[tuple[datetime, datetime | None]] = []
    if config.tipo_cronometro == "Corrido":
        segmentos.append((inicio_partido.timestamp_real, None))
    else:
        numeros = sorted({h.numero_periodo for h in hitos if h.tipo_hito in ("Inicio_Periodo", "Fin_Periodo")})
        for numero in numeros:
            inicio = next(
                (h for h in hitos if h.tipo_hito == "Inicio_Periodo" and h.numero_periodo == numero), None
            )
            if inicio is None:
                continue  # Fin_Periodo sin su Inicio no debería pasar (trigger lo impide)
            fin = next((h for h in hitos if h.tipo_hito == "Fin_Periodo" and h.numero_periodo == numero), None)
            segmentos.append((inicio.timestamp_real, fin.timestamp_real if fin else None))

    if not segmentos:
        # Inicio_Partido ya pasó (modo Periodos) pero ningún período abrió
        # todavía — minuto 0, no None: el partido ya "empezó" a los ojos
        # del operador aunque el reloj de período no haya arrancado.
        return 0

    pausas = [h for h in hitos if h.tipo_hito in ("Pausa", "Reanudacion")]
    total_ms = sum(_ms_corriendo(inicio, fin or ahora, pausas) for inicio, fin in segmentos)
    return int(total_ms // 60_000)
