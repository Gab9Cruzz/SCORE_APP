from app.models.evento_partido import EventoPartido
from app.repositories.evento_partido import EventoPartidoRepository


async def procesar_doble_amarilla(
    *,
    evento_partido_repo: EventoPartidoRepository,
    partido_id: int,
    jugador_id: int,
    equipo_id: int,
    eventos_id_amarilla: int,
    eventos_id_roja: int,
    minuto: int,
) -> EventoPartido | None:
    """Listener de doble amarilla (control-mesa-reactividad-playoffs-
    plan.md, Fase 3 §3): si este jugador ya tiene OTRA Tarjeta Amarilla
    'Registrada' en este partido, autogenera la Tarjeta Roja al mismo
    minuto. Vive como función de módulo, no como método de un servicio —
    mismo criterio que `reglas_cambio.validar_reglas_cambio` (ver su
    docstring): ningún servicio de este repo instancia a otro, cada
    caller pasa su propio `EventoPartidoRepository`.

    Dedup explícito contra rojas ya existentes: si el operador TAMBIÉN
    carga la roja a mano (antes o después de que esto dispare), el
    segundo insert ve la primera ya flusheada y no hace nada — evita 2
    rojas para el mismo jugador (no hay constraint única en
    EVENTOS_PARTIDO sobre (jugador_id, eventos_id) que lo impida).

    Llamado SOLO desde el servidor (EventoPartidoService.create y
    PartidoService.registrar_resultado_directo) — el cliente únicamente
    previsualiza esta misma condición para render, nunca inserta el
    evento sintético él mismo (evita el doble-insert que describe el
    plan: el batch de resultado-directo se procesa evento por evento, y
    un elemento sintético agregado por el cliente llegaría DESPUÉS de que
    el servidor ya disparó su propio auto-insert al procesar la 2ª
    amarilla).

    Devuelve un `EventoPartido` SIN PERSISTIR (ni `add`, ni `flush`, ni
    `commit`) — a propósito: los dos callers arman todo con
    `session.add()`+`flush()` y commitean UNA sola vez al final (A1,
    docs/plans/cierre-pendientes-todos-plan.md, unificó a
    `EventoPartidoService.create` con la disciplina que ya tenía
    `PartidoService.registrar_resultado_directo` — antes divergían: éste
    commiteaba una vez al final, aquél commiteaba por evento vía
    `repo.create()`, lo que liberaba el lock del partido ANTES de que este
    listener contara las amarillas). Si esta función persistiera ella
    misma, rompería esa atomicidad en cualquiera de los dos. Cada caller
    decide cómo guardarlo."""
    amarillas = await evento_partido_repo.list(
        limit=2,
        partidos_id=partido_id,
        eventos_id=eventos_id_amarilla,
        jugador_id=jugador_id,
        estado="Registrado",
    )
    if len(amarillas) < 2:
        return None

    rojas = await evento_partido_repo.list(
        limit=1,
        partidos_id=partido_id,
        eventos_id=eventos_id_roja,
        jugador_id=jugador_id,
        estado="Registrado",
    )
    if rojas:
        return None

    return EventoPartido(
        partidos_id=partido_id,
        jugador_id=jugador_id,
        equipo_id=equipo_id,
        eventos_id=eventos_id_roja,
        jugador_id_entra=None,
        minuto=minuto,
    )
