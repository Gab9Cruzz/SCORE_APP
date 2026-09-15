from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    get_current_user,
    get_current_user_optional,
    require_roles,
    require_torneo_access,
    require_torneo_access_de,
)
from app.db.session import get_db
from app.models.usuario import Usuario
from app.exceptions.errors import NotFoundError
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
from app.repositories.disciplina import DisciplinaRepository
from app.repositories.partido import PartidoRepository
from app.schemas.hito_partido import (
    DeshacerCierreForzadoOut,
    DuracionPartidoOut,
    EstadoCronometroOut,
    HitoPartidoCreate,
    HitoPartidoOut,
    HitoPartidoUpdate,
    PreflightInicioOut,
)
from app.schemas.convocado_a_partido import ConvocadoAgregarRequest, ConvocadoOut, ConvocatoriaSetRequest
from app.schemas.partido import (
    EstadoPartido,
    FeedResponseOut,
    PartidoCreate,
    PartidoOut,
    PartidoUpdate,
    ResultadoDirectoCreate,
    WalkoverRequest,
)
from app.services.convocado_a_partido import ConvocadoAPartidoService
from app.services.estadisticas import EstadisticasService
from app.services.feed import FeedService
from app.services.hito_partido import HitoPartidoService
from app.services.partido import PartidoService

router = APIRouter(prefix="/partidos", tags=["Partidos"])


# Resolvers de torneo_id (rbac-licencias-torneos-plan.md, Fase 2) —
# Partido.torneo_id es directo. "Arbitro" pasa como rol sin scoping en
# TODAS las rutas compartidas con TorneoAdmin: ya tiene su propio
# ownership-check (verificar_arbitro_asignado, services/permisos.py) —
# aplicarle además el scoping de TorneoAdmin sería incorrecto, no un
# refuerzo (un Árbitro no tiene ni necesita fila en ASIGNACION_TORNEO_ADMIN).
async def _torneo_id_del_body(data: PartidoCreate) -> int:
    return data.torneo_id


async def _torneo_id_de_partido(partido_id: int, session: AsyncSession = Depends(get_db)) -> int:
    partido = await PartidoRepository(session).get_or_404(partido_id)
    return partido.torneo_id


@router.get("/feed", response_model=FeedResponseOut)
async def feed_partidos(
    disciplina_id: int | None = None,
    # F3: `deporte` (slug) es el que un deep link de WhatsApp manda
    # (`/?deporte=futbol`) — disciplina_id (numérico) queda para
    # consumidores que ya lo tienen resuelto (la propia barra pública).
    # Si vienen los dos, gana disciplina_id (más específico, sin
    # ambigüedad de mayúsculas/tildes).
    deporte: str | None = None,
    fecha: date | None = None,
    limit: int = Query(default=200, le=200),
    # F5: 7 en la carga inicial (sin `fecha` en la URL) — D3/E-G3.
    # Navegar explícito a una fecha manda 0: ese día no tiene fallback,
    # se ve exactamente lo que ese día tiene (o su empty state real).
    ventana_fallback_dias: int = Query(default=7, ge=0, le=7),
    session: AsyncSession = Depends(get_db),
) -> FeedResponseOut:
    """Portal Público (portal-publico-feed-partidos-plan.md, T3.3/C12):
    partidos de UN día, público, sin auth. Va ANTES de `/{partido_id}` en
    este router para que FastAPI no interprete "feed" como un id.

    No es una lista plana — devuelve un envelope con `fecha_pedida` (la
    pedida) y `fecha_efectiva` (la que en verdad se muestra: sin `fecha`,
    o con `ventana_fallback_dias>0`, cae a la fecha publicada más cercana
    — atrás primero, después adelante, acotada a `ventana_fallback_dias`
    días). El corte por `limit` respeta el borde de un bloque de
    torneo — puede devolver más filas que `limit` (el bloque completo
    entra siempre), nunca corta un torneo a la mitad. Ver
    `FeedService.obtener_feed` para el detalle completo.

    Ejemplo: `GET /api/v1/partidos/feed?disciplina_id=1&limit=20`.
    """
    disciplina_id_resuelto = disciplina_id
    if disciplina_id_resuelto is None and deporte:
        encontradas = await DisciplinaRepository(session).list(slug=deporte, limit=1)
        if not encontradas:
            raise NotFoundError("Disciplina", deporte)
        disciplina_id_resuelto = encontradas[0].id
    return await FeedService(session).obtener_feed(
        fecha_pedida=fecha,
        disciplina_id=disciplina_id_resuelto,
        limit=limit,
        ventana_fallback_dias=ventana_fallback_dias,
    )


@router.get("", response_model=list[PartidoOut])
async def listar_partidos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    torneo_id: int | None = None,
    estado: EstadoPartido | None = None,
    arbitro_id: int | None = None,
    # control-mesa-centralizacion-fixture-plan.md, ítem 1: mismo opt-in que
    # GET /torneos?solo_mios=true (E1) — filtra a los torneos asignados
    # cuando el caller es TorneoAdmin, sin efecto para AdminGeneral/Arbitro/
    # anónimo. Es lo que scopea la lista de /control-de-mesa: hoy mezclaba
    # TODOS los torneos del sistema para cualquier TorneoAdmin.
    solo_mios: bool = False,
    # Cascada de archivado (cascada-archivado-alineaciones-traspasos-plan.md,
    # P4): sin esto, la lista de /control-de-mesa trae por igual partidos
    # 'Programado' de un torneo cuyo TORNEO_GRUPO está Archivado. Ningún
    # consumidor actual lo pasa `True` — ver PartidoRepository.list para
    # por qué NO hay excepción por `torneo_id` explícito acá (a diferencia
    # de `torneo_grupo_id` en GET /torneos).
    incluir_archivados: bool = False,
    session: AsyncSession = Depends(get_db),
    usuario: Usuario | None = Depends(get_current_user_optional),
) -> list[PartidoOut]:
    """Público, sin auth (roles-3-modulos-plan.md, Fase 1: los resultados
    ya son públicos a propósito). `arbitro_id` (Fase 3, D1) es un filtro
    más, no un chequeo de permiso: PartidoOut ya expone arbitro_id en
    cada fila, así que este query param no agrega ninguna fuga nueva,
    solo evita filtrar del lado del cliente."""
    torneo_ids_permitidos: list[int] | None = None
    if solo_mios and usuario is not None and usuario.rol == "TorneoAdmin":
        torneo_ids_permitidos = await AsignacionTorneoAdminRepository(session).listar_torneo_ids_activos(usuario.id)
    return await PartidoService(session).list(
        skip=skip,
        limit=limit,
        torneo_id=torneo_id,
        estado=estado,
        arbitro_id=arbitro_id,
        torneo_ids_permitidos=torneo_ids_permitidos,
        incluir_archivados=incluir_archivados,
        # E-B3a (portal-publico-feed-partidos-plan.md): mismo criterio que
        # GET /torneos — un anónimo no debe poder enumerar el fixture de
        # un torneo despublicado por esta vía, aunque su detalle 404ee.
        solo_publicados=usuario is None,
    )


@router.get("/{partido_id}", response_model=PartidoOut)
async def obtener_partido(partido_id: int, session: AsyncSession = Depends(get_db)) -> PartidoOut:
    return await PartidoService(session).get(partido_id)


@router.post(
    "",
    response_model=PartidoOut,
    status_code=201,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_del_body)),
    ],
)
async def crear_partido(data: PartidoCreate, session: AsyncSession = Depends(get_db)) -> PartidoOut:
    """Programa un partido. trg_partidos_validar_inscripcion (06_triggers.sql)
    rechaza si alguno de los dos equipos no está inscrito y no cancelado en
    el torneo — el error llega como 400 con el mensaje del trigger.

    Árbitro NO tiene este endpoint (roles-3-modulos-plan.md, Fase 1, D4):
    crear partidos es de TorneoAdmin/AdminGeneral. Árbitro solo carga
    partidos que ya le asignaron."""
    return await PartidoService(session).create(data)


@router.patch(
    "/{partido_id}",
    response_model=PartidoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def actualizar_partido(
    partido_id: int,
    data: PartidoUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> PartidoOut:
    """Árbitro conserva este endpoint para avanzar el estado de SU partido
    (Programado -> En curso -> Finalizado). El chequeo de "¿es tuyo?" vive
    en PartidoService.update(), no acá (D5)."""
    return await PartidoService(session).update(partido_id, data, usuario_actual)


@router.delete(
    "/{partido_id}",
    response_model=PartidoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin")),
        Depends(require_torneo_access_de(_torneo_id_de_partido)),
    ],
)
async def cancelar_partido(partido_id: int, session: AsyncSession = Depends(get_db)) -> PartidoOut:
    """Borrado lógico -> Estado='Cancelado' (no 'Inactivo': no es un valor
    válido para partidos.estado, ver chk_partidos_estado)."""
    return await PartidoService(session).soft_delete(partido_id)


@router.post(
    "/{partido_id}/walkover",
    response_model=PartidoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def marcar_walkover(
    partido_id: int,
    data: WalkoverRequest,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> PartidoOut:
    """3B-13 (docs/plans/cierre-backlog-todos-plan.md): cierra el partido
    3-0 por ausencia. Ver PartidoService.marcar_walkover para cuándo está
    permitido (Eliminación siempre, Liga/fase de grupos solo si el
    torneo lo habilitó)."""
    return await PartidoService(session).marcar_walkover(partido_id, data.equipo_ausente_id, usuario_actual)


@router.post(
    "/{partido_id}/resultado-directo",
    response_model=PartidoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def registrar_resultado_directo(
    partido_id: int,
    data: ResultadoDirectoCreate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> PartidoOut:
    """"Cargar resultado directo" desde Control de Mesa (control-mesa-
    centralizacion-fixture-plan.md, Sección 5, Alternativa A) — cierra un
    partido 'Programado' de una sola vez (goles/tarjetas/cambios + inicio y
    fin), sin pasar por el cronómetro en vivo. Ver
    PartidoService.registrar_resultado_directo para la garantía de
    atomicidad (todo-o-nada)."""
    return await PartidoService(session).registrar_resultado_directo(partido_id, data, usuario_actual)


# ------------------------------------------------------------
# Motor de Tiempos + Control de Mesa en vivo
# (gestion-avanzada-equipos-control-mesa-plan.md, Fase 3)
# ------------------------------------------------------------


@router.get("/{partido_id}/duracion", response_model=DuracionPartidoOut)
async def obtener_duracion_partido(
    partido_id: int, session: AsyncSession = Depends(get_db)
) -> DuracionPartidoOut:
    """Público, sin auth (mismo criterio que el resto de /partidos y
    /estadisticas — los resultados ya son públicos). Expone
    vw_duracion_partido; todos los campos None significa "sin dato
    todavía" (partido sin Fin_Partido), no un error."""
    return await EstadisticasService(session).duracion_partido(partido_id)


@router.get("/{partido_id}/cronometro", response_model=EstadoCronometroOut)
async def obtener_estado_cronometro(
    partido_id: int, session: AsyncSession = Depends(get_db)
) -> EstadoCronometroOut:
    """Estado calculado del cronómetro + qué hitos son válidos a
    continuación — el frontend no reimplementa la máquina de estados
    (Fase 3 del plan)."""
    return await HitoPartidoService(session).estado_cronometro(partido_id)


@router.post(
    "/{partido_id}/hitos",
    response_model=HitoPartidoOut,
    status_code=201,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def registrar_hito_partido(
    partido_id: int,
    data: HitoPartidoCreate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> HitoPartidoOut:
    """Crea un Hito (Inicio/Fin de partido o período, Pausa/Reanudación).
    trg_hito_sincroniza_estado (06_triggers.sql) sincroniza PARTIDOS.Estado
    automáticamente con Inicio_Partido/Fin_Partido — se recomienda que el
    botón "Empezar Partido" del dashboard dispare este endpoint (con
    tipo_hito='Inicio_Partido') en vez del PATCH directo, para que el
    partido siempre tenga un Inicio_Partido auditable (necesario para
    vw_duracion_partido)."""
    return await HitoPartidoService(session).registrar(partido_id, data, usuario_actual)


@router.post(
    "/{partido_id}/deshacer-cierre-forzado",
    response_model=DeshacerCierreForzadoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def deshacer_cierre_forzado(
    partido_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> DeshacerCierreForzadoOut:
    """Área 4 (T17) — deshace un "Fin de Partido forzado" reciente, solo
    dentro de la ventana de gracia calculada server-side (ver
    HitoPartidoService.deshacer_fin_forzado para las 3 guardas). Mismo
    ownership-check que el resto de este router (árbitro asignado o
    scoping de torneo — sin rol nuevo)."""
    return await HitoPartidoService(session).deshacer_fin_forzado(partido_id, usuario_actual)


@router.patch(
    "/{partido_id}/hitos/{hito_id}",
    response_model=HitoPartidoOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def corregir_hito_partido(
    partido_id: int,
    hito_id: int,
    data: HitoPartidoUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> HitoPartidoOut:
    """Corrección de Minuto_Reloj/Timestamp_Real de un hito ya cargado
    (Flujo 5 del plan)."""
    return await HitoPartidoService(session).corregir(partido_id, hito_id, data, usuario_actual)


# Convocados/titular-suplente (3B-2, docs/plans/cierre-backlog-todos-plan.md)
# — público en lectura (mismo criterio que el resto de este router: quien
# mira el partido puede ver la convocatoria), solo TorneoAdmin/el Árbitro
# asignado la arma.
@router.get("/{partido_id}/convocados", response_model=list[ConvocadoOut])
async def listar_convocados(partido_id: int, session: AsyncSession = Depends(get_db)) -> list[ConvocadoOut]:
    convocados = await ConvocadoAPartidoService(session).listar(partido_id)
    return [ConvocadoOut.model_validate(c) for c in convocados]


@router.put(
    "/{partido_id}/convocados",
    response_model=list[ConvocadoOut],
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def definir_convocados(
    partido_id: int,
    data: ConvocatoriaSetRequest,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> list[ConvocadoOut]:
    """Reemplaza la convocatoria ENTERA del partido de una sola vez — ver
    ConvocatoriaSetRequest. Una lista vacía es válida: saca la
    convocatoria (vuelve a "toda la plantilla es candidata")."""
    convocados = await ConvocadoAPartidoService(session).reemplazar(partido_id, data, usuario_actual)
    return [ConvocadoOut.model_validate(c) for c in convocados]


@router.post(
    "/{partido_id}/convocados",
    response_model=ConvocadoOut,
    status_code=201,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def agregar_convocado(
    partido_id: int,
    data: ConvocadoAgregarRequest,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> ConvocadoOut:
    """Suma UN convocado sin tocar el resto de la alineación
    (gestionar-partido-alineaciones-plan.md, D3 revisada).

    Es el camino de las llegadas tardías: a diferencia del PUT, que reescribe
    la lista entera y solo se acepta antes del arranque, esto es aditivo y por
    lo tanto funciona con el partido EN CURSO sin tocar el cronómetro ni el
    `titular` de nadie. Idempotente ante un doble-tap."""
    convocado = await ConvocadoAPartidoService(session).agregar(partido_id, data, usuario_actual)
    return ConvocadoOut.model_validate(convocado)


@router.get(
    "/{partido_id}/preflight-inicio",
    response_model=PreflightInicioOut,
    dependencies=[
        Depends(require_roles("TorneoAdmin", "Arbitro")),
        Depends(require_torneo_access_de(_torneo_id_de_partido, "Arbitro")),
    ],
)
async def preflight_inicio_partido(
    partido_id: int, session: AsyncSession = Depends(get_db)
) -> PreflightInicioOut:
    """¿Se puede tocar "Empezar Partido"? (H1-eng del plan).

    Endpoint propio y AUTENTICADO en vez de campos nuevos en
    `GET /partidos/{id}/cronometro`: ese es público sin auth y lo pollean cada
    5 segundos `Cronometro.tsx` y `PartidoEnVivo.tsx` de forma anónima, así que
    sumarle el cálculo de titulares (~7 queries, con un roster completo por
    equipo) lo convertiría en el endpoint más caro del sistema.

    El frontend NO reimplementa la regla: consume `puede_iniciar` y
    `motivo_bloqueo`, que salen del mismo código que aplica el gate real."""
    return await HitoPartidoService(session).preflight_inicio(partido_id)
