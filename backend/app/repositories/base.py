"""CRUD genérico con borrado lógico.

El comentario en 02_constraints.sql es explícito: la API usa borrado lógico
(Estado='Inactivo') y nunca expone un DELETE físico, porque 6 FK tienen ON
DELETE CASCADE y arrastrarían inscripciones, partidos y eventos. Por eso este
repositorio no tiene un método `delete`, solo `soft_delete`.
"""
from __future__ import annotations

from collections.abc import Sequence
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import CampoObligatorioError, NotFoundError

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    model: type[ModelT]
    nombre_recurso: str

    def __init__(self, session: AsyncSession):
        self.session = session

    async def get(self, id_: int) -> ModelT | None:
        return await self.session.get(self.model, id_)

    async def get_or_404(self, id_: int) -> ModelT:
        obj = await self.get(id_)
        if obj is None:
            raise NotFoundError(self.nombre_recurso, id_)
        return obj

    def _consulta_filtrada(self, ids: Sequence[int] | None = None, **filtros: Any) -> Select:
        """Igualdad por columna para cada filtro no nulo. `ids` (TASK-039)
        restringe a esos identificadores: es lo que usa el frontend para
        traducir varios ids a nombres en una sola petición."""
        stmt = select(self.model)
        if ids is not None:
            stmt = stmt.where(self.model.id.in_(ids))  # type: ignore[attr-defined]
        for campo, valor in filtros.items():
            if valor is not None:
                stmt = stmt.where(getattr(self.model, campo) == valor)
        return stmt

    async def _contar(self, stmt: Select) -> int:
        """Total de filas de `stmt` sin paginar (TASK-011): mismo filtro que
        el listado, para la cabecera X-Total-Count."""
        subconsulta = stmt.order_by(None).subquery()
        result = await self.session.execute(select(func.count()).select_from(subconsulta))
        return result.scalar_one()

    async def contar_filtrado(self, **filtros: Any) -> int:
        """Lo que contaría `list(**filtros)` sin `skip`/`limit`."""
        return await self._contar(self._consulta_filtrada(**filtros))

    async def list(self, skip: int = 0, limit: int = 100, **filtros: Any) -> list[ModelT]:
        stmt = self._consulta_filtrada(**filtros)
        stmt = stmt.order_by(self.model.id).offset(skip).limit(limit)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def create(self, commit: bool = True, **datos: Any) -> ModelT:
        """Commitea de inmediato — un caller que necesite insertar más de
        una fila en la MISMA transacción (ej. un evento + una roja
        automática, o varios eventos de un resultado directo) no puede usar
        esto: tiene que armar el/los objeto(s) con `session.add()` +
        `flush()` y commitear una sola vez al final, a mano (ver
        `PartidoService.registrar_resultado_directo` y, desde A1 —
        docs/plans/cierre-pendientes-todos-plan.md —,
        `EventoPartidoService._crear_bajo_lock`, que dejó de usar este
        método por esa misma razón: antes el commit acá adentro liberaba el
        lock del partido antes de que el listener de doble amarilla
        contara las tarjetas). El próximo que lea "create no commitea" en
        otro repo no debería "arreglar" ESTE método para que se le parezca
        — es a propósito que sea el caso simple."""
        obj = self.model(**datos)
        self.session.add(obj)
        await self._confirmar(obj, commit)
        return obj

    async def _confirmar(self, obj: ModelT, commit: bool) -> None:
        """TASK-022 (BE-02): `commit=False` hace flush (asigna ids, corren
        los triggers) sin confirmar, para que un caso de uso de varios pasos
        confirme UNA vez al final y un fallo en cualquier paso no deje nada a
        medias. El default sigue siendo confirmar para no cambiar a todos
        los llamadores de una vez; el objetivo es invertirlo."""
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        # fecha_modificacion la pisa el trigger fn_actualizar_fecha_modificacion
        # (06_triggers.sql) en el UPDATE; refresh trae ese valor real de vuelta.
        await self.session.refresh(obj)

    async def update(self, id_: int, **datos: Any) -> ModelT:
        obj = await self.get_or_404(id_)
        return await self.save_changes(obj, **datos)

    async def save_changes(self, obj: ModelT, commit: bool = True, **datos: Any) -> ModelT:
        """Igual que `update`, pero recibe el objeto ya cargado.

        Separado de `update` para que un caller que necesite hacer algo con
        el objeto ANTES de mutarlo (ej: el ownership-check de Árbitro en
        roles-3-modulos-plan.md Fase 1) no tenga que cargarlo dos veces —
        una para el chequeo y otra dentro de `update`.

        TASK-020 (FUN-10): escribe TODO lo que recibe, `None` incluido — un
        `null` explícito limpia el campo. Antes los `None` se descartaban y no
        había forma de vaciar nada. Por eso los llamadores pasan solo lo que
        quieren escribir (`model_dump(exclude_unset=True)` en los PATCH). Un
        `None` en una columna que no admite vacío es 422.
        """
        columnas = obj.__mapper__.columns
        for campo, valor in datos.items():
            if valor is None and campo in columnas and not columnas[campo].nullable:
                raise CampoObligatorioError(campo)
        for campo, valor in datos.items():
            setattr(obj, campo, valor)
        await self._confirmar(obj, commit)
        return obj

    async def soft_delete(self, id_: int, estado_inactivo: str = "Inactivo") -> ModelT:
        obj = await self.get_or_404(id_)
        # Atributo transiente (no una columna: no se mapea ni se persiste),
        # leído y borrado por el event listener de app/core/auditoria.py.
        # Es lo único que distingue "esto fue una baja lógica" de "se
        # modificó cualquier otro campo" sin adivinar por el nombre/valor
        # de Estado — que también cambia en transiciones de negocio
        # normales (ej. Torneo -> 'Finalizado') que no son una baja.
        obj._auditoria_accion = "eliminar"  # type: ignore[attr-defined]
        return await self.save_changes(obj, estado=estado_inactivo)

