from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, func, select

from app.models.acceso import Acceso
from app.repositories.base import BaseRepository


class AccesoRepository(BaseRepository[Acceso]):
    """Solo escritura de altas y lectura. No hereda `update` ni
    `soft_delete` de forma útil a propósito: una bitácora que se puede
    editar o dar de baja deja de servir como bitácora. `BaseRepository`
    los trae igual, pero ningún service ni router los expone."""

    model = Acceso
    nombre_recurso = "Acceso"

    async def listar(
        self,
        skip: int = 0,
        limit: int = 100,
        usuario_id: int | None = None,
        username: str | None = None,
        exitoso: bool | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Acceso]:
        """Lo último primero — el orden inverso al de `BaseRepository.list`
        (que ordena por id ascendente). En una bitácora, la fila que
        importa es la más reciente: si esto listara del principio, con
        cualquier volumen real la primera página serían los accesos del
        día que se instaló el sistema.

        `username` filtra por coincidencia parcial, sin distinguir
        mayúsculas: quien audita suele acordarse de un pedazo del nombre,
        no del string exacto — y en los intentos fallidos el username es
        texto arbitrario que nunca fue una cuenta.
        """
        stmt = select(Acceso)
        if usuario_id is not None:
            stmt = stmt.where(Acceso.usuario_id == usuario_id)
        if username:
            stmt = stmt.where(Acceso.username.ilike(f"%{username}%"))
        if exitoso is not None:
            stmt = stmt.where(Acceso.exitoso == exitoso)
        if desde is not None:
            stmt = stmt.where(Acceso.fecha >= datetime.combine(desde, time.min))
        if hasta is not None:
            # `hasta` es un día, no un instante: se incluye ese día entero.
            # Sin esto, filtrar "hasta hoy" no devolvería nada de hoy, que
            # es justo lo que alguien auditando espera ver.
            stmt = stmt.where(Acceso.fecha <= datetime.combine(hasta, time.max))
        stmt = stmt.order_by(Acceso.fecha.desc(), Acceso.id.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def purgar_anteriores_a(self, dias: int) -> int:
        """Borra las filas más viejas que `dias` y devuelve cuántas fueron.

        Es la única operación destructiva sobre esta tabla, y vive solo
        acá: no hay endpoint que la dispare (ver routes/accesos.py — una
        bitácora que se puede vaciar por HTTP no sirve como evidencia). La
        llama el arranque de la API con el valor de configuración.

        `dias <= 0` significa "no purgar nunca" y sale sin tocar nada — así
        apagar la retención es cambiar un número en el .env, no comentar
        código.

        El corte se calcula contra la hora de la aplicación, no con
        `now()` de Postgres: es el mismo reloj con el que se escribieron
        las filas (Fecha viene del DEFAULT del servidor, pero ambos corren
        en la misma máquina en este proyecto) y hace la función testeable
        sin depender de la hora de la base.
        """
        if dias <= 0:
            return 0
        corte = datetime.now() - timedelta(days=dias)
        result = await self.session.execute(delete(Acceso).where(Acceso.fecha < corte))
        await self.session.commit()
        return result.rowcount or 0

    async def contar(self) -> int:
        """Total de filas — para poder decir en el log cuántas quedaron."""
        result = await self.session.execute(select(func.count()).select_from(Acceso))
        return result.scalar_one()
