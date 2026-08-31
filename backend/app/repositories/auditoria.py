from datetime import date, datetime, time, timedelta

from sqlalchemy import delete, func, select

from app.models.auditoria import Auditoria
from app.repositories.base import BaseRepository


class AuditoriaRepository(BaseRepository[Auditoria]):
    """Solo escritura (del event listener de `core/auditoria.py`) y lectura.

    Mismo criterio que `AccesoRepository`: no hereda `update` ni
    `soft_delete` de forma útil a propósito — una bitácora editable deja de
    servir como evidencia. Tampoco hay un `create()` que un service llame:
    las filas las escribe el listener directo con Core, nunca esta clase.
    """

    model = Auditoria
    nombre_recurso = "Auditoria"

    async def listar(
        self,
        skip: int = 0,
        limit: int = 100,
        tabla: str | None = None,
        registro_id: int | None = None,
        accion: str | None = None,
        usuario_id: int | None = None,
        desde: date | None = None,
        hasta: date | None = None,
    ) -> list[Auditoria]:
        """Lo último primero, igual que `AccesoRepository.listar` — mismo
        razonamiento: en una bitácora, lo que importa es lo más reciente.

        `hasta` incluye el día entero (ver `AccesoRepository.listar` para
        el porqué de `time.max`).
        """
        stmt = select(Auditoria)
        if tabla:
            stmt = stmt.where(Auditoria.tabla == tabla)
        if registro_id is not None:
            stmt = stmt.where(Auditoria.registro_id == registro_id)
        if accion:
            stmt = stmt.where(Auditoria.accion == accion)
        if usuario_id is not None:
            stmt = stmt.where(Auditoria.usuario_id == usuario_id)
        if desde is not None:
            stmt = stmt.where(Auditoria.fecha >= datetime.combine(desde, time.min))
        if hasta is not None:
            stmt = stmt.where(Auditoria.fecha <= datetime.combine(hasta, time.max))
        stmt = stmt.order_by(Auditoria.fecha.desc(), Auditoria.id.desc()).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def purgar_anteriores_a(self, dias: int) -> int:
        """Idéntica en forma a `AccesoRepository.purgar_anteriores_a` — ver
        ahí para el razonamiento completo (corte contra `datetime.now()` de
        la app, `dias <= 0` = no purgar nunca)."""
        if dias <= 0:
            return 0
        corte = datetime.now() - timedelta(days=dias)
        result = await self.session.execute(delete(Auditoria).where(Auditoria.fecha < corte))
        await self.session.commit()
        return result.rowcount or 0

    async def contar(self) -> int:
        result = await self.session.execute(select(func.count()).select_from(Auditoria))
        return result.scalar_one()
