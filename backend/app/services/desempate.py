"""Desempate de eliminatoria: tiempo extra y penales
(docs/plans/desempate-tiempo-extra-penales-plan.md, D3/§5).

Lógica de escritura PEQUEÑA y compartida por los tres caminos que pueden
cerrar un partido de Eliminación con un empate: el cronómetro en vivo
(HitoPartidoService.registrar/_registrar_fin_forzado) y la carga directa
(PartidoService.registrar_resultado_directo), más el PATCH genérico
(PartidoService.update). D-A2/D-Q2 piden una sola fuente de verdad para la
VALIDACIÓN (una función en el trigger); esto es su espejo del lado de qué
se ESCRIBE, para que los tres caminos deriven las mismas columnas de la
misma manera en vez de reimplementar la regla cada uno a su modo.
"""

from app.exceptions.errors import DomainRuleError


def validar_metodo_desempate_eliminatoria(metodo: str, tipo_cronometro: str) -> None:
    """D5/§7: guarda compartida por `TorneoService` (create/update) y
    `MotorFormatosService.generar_playoffs` — un torneo `Corrido` (Tenis/
    Pádel/Ajedrez/LoL, sin marcador de goles) no tiene "tiempo extra" ni
    "penales" en este sentido; su empate se resuelve con
    `Ganador_Corrido_ID` por partido. Función libre (no un método de
    `TorneoService`) para que `MotorFormatosService` no tenga que
    instanciar un servicio ajeno solo para este chequeo."""
    if tipo_cronometro == "Corrido" and metodo != "Manual":
        raise DomainRuleError(
            "Este torneo usa cronómetro corrido (sin marcador de goles) — el método de desempate "
            "de eliminatoria tiene que quedar en 'Lo decido yo al cerrar el partido'."
        )


def completar_metodo_manual(ganador_desempate_id: int | None, metodo_desempate: str | None) -> str | None:
    """SPEC-REVIEW F1 (BLOCKING): los tres caminos que ya escriben
    `ganador_desempate_id` hoy (el radio "¿quién avanza?" en vivo, el
    cierre forzado, y el PATCH genérico vía `PartidoUpdate`) no saben
    mandar `metodo_desempate` — sin este default, la migración 33 hace
    que TODOS empiecen a fallar con `desempate_sin_metodo`
    (`Ganador_Desempate_ID NOT NULL => Metodo_Desempate NOT NULL`).
    `None` cuando no vino ganador: no hay nada que completar."""
    if metodo_desempate is None and ganador_desempate_id is not None:
        return "Manual"
    return metodo_desempate


def derivar_ganador_desde_penales(
    penales_local: int | None,
    penales_visitante: int | None,
    equipo_local_id: int | None,
    equipo_visitante_id: int | None,
) -> int | None:
    """D-D4 (HIGH): el ganador de la tanda se deriva SIEMPRE del marcador
    de penales acá, nunca se confía en un `ganador_desempate_id` que el
    cliente calculó por su cuenta — una tanda 4-2 cargada con los goles al
    revés (fácil de confundir en una VUELTA, cuyo encabezado muestra el
    GLOBAL con localía cruzada) pasaría todas las reglas de forma del
    trigger y avanzaría al equipo equivocado si se confiara en el cliente.
    `None` si no hay tanda que resolver (penales_local es None)."""
    if penales_local is None or penales_visitante is None:
        return None
    return equipo_local_id if penales_local > penales_visitante else equipo_visitante_id


def es_escape_manual_sobre_metodo_configurado(metodo_resuelto: str | None, metodo_aplicable: str | None) -> bool:
    """D-A1 (deliberado, no un agujero): un partido de un torneo
    configurado con `Penales_Directo` puede seguir cerrándose `Manual`
    (resultado directo / hoja de papel) — el escape hatch que mantiene
    honesta la carga en papel. Tiene que quedar LOGUEADO como
    `desempate_manual_sobre_metodo_configurado` y contado por la métrica 3
    (§12-bis): si la tasa es alta, es señal de que el flujo en vivo no se
    parece a la realidad de la cancha, no un error a rechazar."""
    return metodo_resuelto == "Manual" and metodo_aplicable is not None and metodo_aplicable != "Manual"


def resolver_metodo_desempate_aplicable(metodo_eliminatoria: str, ronda_nombre: str | None) -> str:
    """D6/§8: snapshot de la regla del TORNEO a un método CONCRETO para
    ESTE partido, tomado en el momento en que arranca. Solo se llama para
    partidos de fase Eliminación (el caller decide eso).

    Fase 2 (esta función, tal como está): identidad — 'Manual' y
    'Penales_Directo' ya son valores concretos, no reglas de cuadro.
    Fase 3 agrega acá, y SOLO acá, la resolución de 'Penales_Salvo_Final'
    (keyed a `ronda_nombre == 'Final'`, NUNCA al parámetro `es_final` de
    `motor_formatos.py` — SPEC-REVIEW S11: `_crear_llave(..., "Tercer
    Lugar", "Unico", es_final=True, ...)` pasa `es_final=True` para el
    Tercer Lugar, así que keyear por ese flag daría lo contrario de lo
    buscado). `ronda_nombre` ya se recibe acá, sin usar, precisamente para
    que ese día no haga falta cambiar la firma."""
    return metodo_eliminatoria


def resolver_desempate_resultado_directo(
    *,
    ganador_desempate_id: int | None,
    penales_local: int | None,
    penales_visitante: int | None,
    hubo_tiempo_extra: bool,
    equipo_local_id: int | None,
    equipo_visitante_id: int | None,
    goles_local: int,
    goles_visitante: int,
) -> tuple[str | None, int | None]:
    """Deriva `(metodo_desempate, ganador_desempate_id)` para la carga
    directa (ModalResultadoDirecto) — D-D12/E4, SPEC-REVIEW F9.

    Precedencia (más específico primero):
    1. Vino el marcador de la tanda (`penales_local`/`visitante`) =>
       'Penales', ganador SIEMPRE derivado de la tanda (nunca del cliente,
       ver `derivar_ganador_desde_penales`).
    2. Se jugó prórroga (`hubo_tiempo_extra`) Y el marcador final YA NO
       está empatado => 'Tiempo_Extra', sin ganador de desempate (el
       marcador de goles decide — `Ganador_Desempate_ID` queda NULL, F9:
       sin esta regla un "2-1 a.e.t." cargado a mano quedaría con
       Hubo_Tiempo_Extra=TRUE y Metodo_Desempate=NULL, una celda
       indefinida en la matriz de render).
    3. "No tengo el marcador de la tanda" (E4): no vino nada de lo de
       arriba => cae a 'Manual' si vino un `ganador_desempate_id` suelto
       (mismo escape hatch de siempre), o `(None, None)` si tampoco vino
       eso — el trigger decide si hacía falta.
    """
    if penales_local is not None and penales_visitante is not None:
        ganador = derivar_ganador_desde_penales(penales_local, penales_visitante, equipo_local_id, equipo_visitante_id)
        return "Penales", ganador
    if hubo_tiempo_extra and goles_local != goles_visitante:
        return "Tiempo_Extra", None
    return completar_metodo_manual(ganador_desempate_id, None), ganador_desempate_id
