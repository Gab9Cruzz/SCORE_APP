from datetime import date

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_roles
from app.db.session import get_db
from app.repositories.acceso import AccesoRepository
from app.schemas.acceso import AccesoOut

router = APIRouter(prefix="/accesos", tags=["Accesos (auditoría)"])

# Solo lectura, y solo AdminGeneral. No hay POST/PATCH/DELETE a propósito:
# las filas las escribe UsuarioService.login() y nadie más. Una bitácora
# con endpoint de escritura o de borrado se puede falsificar desde afuera,
# y entonces deja de servir para lo único que sirve.
#
# El gate es más estricto que el de /usuarios (que TorneoAdmin puede leer
# recortado): acá cada fila dice quién entró, desde qué IP y con qué
# navegador. Es dato de seguridad de todas las cuentas, incluidas las que
# un TorneoAdmin no debería ni saber que existen.


@router.get("", response_model=list[AccesoOut], dependencies=[Depends(require_roles("AdminGeneral"))])
async def listar_accesos(
    skip: int = 0,
    limit: int = Query(default=100, le=200),
    usuario_id: int | None = None,
    username: str | None = None,
    exitoso: bool | None = None,
    desde: date | None = None,
    hasta: date | None = None,
    session: AsyncSession = Depends(get_db),
) -> list[AccesoOut]:
    """Bitácora de inicios de sesión, del más reciente al más antiguo.

    `username` es coincidencia parcial e insensible a mayúsculas; `desde`
    y `hasta` son días completos (incluyen el día indicado entero).
    """
    return await AccesoRepository(session).listar(
        skip=skip,
        limit=limit,
        usuario_id=usuario_id,
        username=username,
        exitoso=exitoso,
        desde=desde,
        hasta=hasta,
    )
