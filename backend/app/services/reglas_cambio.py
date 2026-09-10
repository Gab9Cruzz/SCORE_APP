from app.exceptions.errors import DomainRuleError
from app.models.torneo import Torneo
from app.repositories.evento_partido import EventoPartidoRepository


async def validar_reglas_cambio(
    *,
    torneo: Torneo,
    evento_catalogo_nombre: str,
    evento_partido_repo: EventoPartidoRepository,
    partido_id: int,
    jugador_id: int,
    jugador_id_entra: int | None,
    equipo_id: int,
    eventos_id: int,
) -> None:
    """Reglas de negocio de "Cambio" (sustitución) — tope de cantidad,
    no-retorno y doble-salida, gobernadas por `Torneo.maximo_cambios_por_equipo`/
    `Torneo.permite_cambios_ilimitados`. Solo aplica a tipo_hito='Cambio';
    cualquier otro evento (Gol, Autogol, tarjetas) no toca esto.

    Vive como función module-level, no como método de un servicio
    (goles-por-marcador-slots-plan.md, Fase 3 Eng, corrección 3): antes de
    esta corrección, `PartidoService.registrar_resultado_directo` iba a
    "reusar" `EventoPartidoService._validar_reglas_cambio`, un método
    PRIVADO de otra clase — ningún servicio de este repo instancia a otro
    (`grep "Service(session)" app/services` no encuentra ningún caso). Cada
    servicio (`EventoPartidoService.create`, en vivo, y
    `PartidoService.registrar_resultado_directo`, resultado directo — antes
    NO llamaba nada de esto, hallazgo 6 de ese plan) pasa acá su propio
    `EventoPartidoRepository`, en vez de acoplarse al otro servicio.
    """
    if evento_catalogo_nombre != "Cambio":
        return

    # Doble-salida (corrección 1, CRÍTICO): INCONDICIONAL, fuera del `if`
    # de `permite_cambios_ilimitados` de abajo — ese flag gobierna REINGRESO
    # (`jugador_id_entra` volviendo a entrar más tarde), nunca el
    # doble-registro de la MISMA salida (`jugador_id` saliendo dos veces).
    # Antes de esta corrección, un torneo con cambios ilimitados no tenía
    # NINGUNA protección contra esto — exactamente al revés de lo que
    # "ilimitados" debería significar (gobierna reingreso, no duplicar la
    # salida).
    ya_salio_antes = await evento_partido_repo.list(
        limit=1,
        partidos_id=partido_id,
        eventos_id=eventos_id,
        jugador_id=jugador_id,
        estado="Registrado",
    )
    if ya_salio_antes:
        raise DomainRuleError(
            "Ese jugador ya salió por cambio antes en este partido — no puede "
            "volver a salir (ya generó un evento de Cambio previo)."
        )

    if not torneo.permite_cambios_ilimitados and jugador_id_entra is not None:
        ya_salio = await evento_partido_repo.list(
            limit=1,
            partidos_id=partido_id,
            eventos_id=eventos_id,
            jugador_id=jugador_id_entra,
            estado="Registrado",
        )
        if ya_salio:
            raise DomainRuleError(
                "Ese jugador ya salió por cambio antes en este partido — este torneo no permite "
                "reingresos (cambios rotativos). Activá 'Permite cambios ilimitados' si corresponde."
            )

    if torneo.maximo_cambios_por_equipo is not None:
        usados = await evento_partido_repo.list(
            limit=torneo.maximo_cambios_por_equipo + 1,
            partidos_id=partido_id,
            eventos_id=eventos_id,
            equipo_id=equipo_id,
            estado="Registrado",
        )
        if len(usados) >= torneo.maximo_cambios_por_equipo:
            raise DomainRuleError(
                f"Ya se usaron los {torneo.maximo_cambios_por_equipo} cambios permitidos para "
                "este equipo en este partido."
            )
