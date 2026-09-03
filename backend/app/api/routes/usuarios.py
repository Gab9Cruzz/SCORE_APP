from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, require_roles
from app.db.session import get_db
from app.exceptions.errors import ForbiddenError
from app.models.usuario import Usuario
from app.schemas.usuario import (
    AsignacionTorneosUpdate,
    LicenciaUpdate,
    RolUsuario,
    UsuarioCreate,
    UsuarioOut,
    UsuarioUpdate,
)
from app.services.asignacion_torneo_admin import AsignacionTorneoAdminService
from app.services.usuario import UsuarioService

# Gestión de cuentas (AdminGeneral, TorneoAdmin, Arbitro, Publico).
#
# Escritura (POST/PATCH/DELETE) exige AdminGeneral LITERAL, a propósito —
# no es el swap uniforme Admin->TorneoAdmin que se aplicó en los demás
# routers (roles-3-modulos-plan.md, Fase 1, D3). Si este router pasara a
# aceptar TorneoAdmin en escritura, ese rol heredaría gestión de usuarios,
# incluyendo poder auto-escalarse a AdminGeneral por PATCH — fue un bug
# real encontrado por la voz externa en Fase 1, no lo repitas.
#
# Lectura (GET) SÍ acepta TorneoAdmin desde Fase 2 (D5): necesita ver qué
# usuarios son Árbitro para asignarlos a un partido. UsuarioService.list()/
# get() recortan el resultado a solo cuentas Arbitro para ese rol — el
# require_roles de acá solo decide quién entra al endpoint, no qué ve una
# vez adentro.
router = APIRouter(prefix="/usuarios", tags=["Usuarios"])


@router.get(
    "", response_model=list[UsuarioOut], dependencies=[Depends(require_roles("AdminGeneral", "TorneoAdmin"))]
)
async def listar_usuarios(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    rol: RolUsuario | None = None,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> list[UsuarioOut]:
    return await UsuarioService(session).list(usuario_actual, skip=skip, limit=limit, rol=rol)


@router.get(
    "/{usuario_id}",
    response_model=UsuarioOut,
    dependencies=[Depends(require_roles("AdminGeneral", "TorneoAdmin"))],
)
async def obtener_usuario(
    usuario_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> UsuarioOut:
    return await UsuarioService(session).get(usuario_id, usuario_actual)


@router.post(
    "", response_model=UsuarioOut, status_code=201, dependencies=[Depends(require_roles("AdminGeneral"))]
)
async def crear_usuario(data: UsuarioCreate, session: AsyncSession = Depends(get_db)) -> UsuarioOut:
    return await UsuarioService(session).create(data)


@router.patch(
    "/{usuario_id}", response_model=UsuarioOut, dependencies=[Depends(require_roles("AdminGeneral"))]
)
async def actualizar_usuario(
    usuario_id: int,
    data: UsuarioUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> UsuarioOut:
    """Rechaza que un AdminGeneral se cambie su propio rol o se desactive a
    sí mismo — chequeo en UsuarioService.update() (T6)."""
    return await UsuarioService(session).update(usuario_id, data, usuario_actual)


@router.delete(
    "/{usuario_id}", response_model=UsuarioOut, dependencies=[Depends(require_roles("AdminGeneral"))]
)
async def dar_de_baja_usuario(
    usuario_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> UsuarioOut:
    """Rechaza que un AdminGeneral se desactive a sí mismo — chequeo en
    UsuarioService.soft_delete() (T6)."""
    return await UsuarioService(session).soft_delete(usuario_id, usuario_actual)


# --- Licencia + asignación de torneos (rbac-licencias-torneos-plan.md, §4.5) ---
#
# Mismo criterio que el resto de la escritura de este router: AdminGeneral
# LITERAL, sin el bypass uniforme de require_roles que sí tienen los demás
# routers — otorgar/revocar licencia y reasignar torneos es tan sensible
# como crear/editar cuentas, así que se gatea igual.


@router.patch(
    "/{usuario_id}/licencia",
    response_model=UsuarioOut,
    dependencies=[Depends(require_roles("AdminGeneral"))],
)
async def actualizar_licencia(
    usuario_id: int,
    data: LicenciaUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> UsuarioOut:
    """Rechaza que un AdminGeneral se revoque su propia licencia — chequeo
    en AsignacionTorneoAdminService.set_licencia (clon de T6)."""
    return await AsignacionTorneoAdminService(session).set_licencia(usuario_id, data.activa, usuario_actual)


@router.get("/{usuario_id}/torneos", response_model=list[int])
async def obtener_torneos_asignados(
    usuario_id: int,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> list[int]:
    """AdminGeneral ve cualquier cuenta; TorneoAdmin solo puede consultar
    su PROPIO set (precarga del modal "Gestionar torneos" que él mismo no
    puede abrir para sí — hoy el panel es exclusivo de AdminGeneral, pero
    el endpoint de lectura queda abierto a self por si un TorneoAdmin
    necesita confirmar sus propios torneos desde otra pantalla)."""
    if usuario_actual.rol != "AdminGeneral" and usuario_actual.id != usuario_id:
        raise ForbiddenError("Solo podés consultar tus propios torneos asignados.")
    return await AsignacionTorneoAdminService(session).listar_torneos_asignados(usuario_id)


@router.patch(
    "/{usuario_id}/torneos",
    response_model=list[int],
    dependencies=[Depends(require_roles("AdminGeneral"))],
)
async def actualizar_torneos_asignados(
    usuario_id: int,
    data: AsignacionTorneosUpdate,
    session: AsyncSession = Depends(get_db),
    usuario_actual: Usuario = Depends(get_current_user),
) -> list[int]:
    """Reemplaza el set completo de torneos asignados a `usuario_id`. Sin
    bypass de "self" — solo AdminGeneral, igual que el resto de la
    escritura de este router (comentario del header del archivo)."""
    return await AsignacionTorneoAdminService(session).set_torneos_asignados(usuario_id, data.torneo_ids, usuario_actual)
