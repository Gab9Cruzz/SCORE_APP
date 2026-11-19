from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import ConflictError, DomainRuleError
from app.models.equipo import Equipo
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.torneo import Torneo
from app.repositories.disciplina import DisciplinaRepository
from app.repositories.equipo import EquipoRepository
from app.repositories.modalidad import ModalidadRepository
from app.schemas.equipo import EquipoCreate, EquipoOut, EquipoUpdate


class EquipoService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.repo = EquipoRepository(session)
        self.disciplina_repo = DisciplinaRepository(session)
        self.modalidad_repo = ModalidadRepository(session)

    async def get(self, id_: int) -> EquipoOut:
        return await self._con_plantilla(await self.repo.get_or_404(id_))

    async def list(
        self,
        skip: int = 0,
        limit: int = 100,
        estado: str | None = None,
        disciplina_id: int | None = None,
        modalidad_id: int | None = None,
    ) -> list[EquipoOut]:
        equipos = await self.repo.list(
            skip=skip,
            limit=limit,
            estado=estado,
            disciplina_id=disciplina_id,
            modalidad_id=modalidad_id,
        )
        totales = await self.repo.plantilla_total_por_equipo([e.id for e in equipos])
        return [self._a_salida(e, totales.get(e.id, 0)) for e in equipos]

    async def create(self, data: EquipoCreate) -> EquipoOut:
        await self._validar_disciplina_modalidad(data.disciplina_id, data.modalidad_id)
        equipo = await self.repo.create(**data.model_dump())
        # Recién creado: plantilla 0 por definición (Decisión #1 = A1 — la
        # plantilla se carga al inscribirlo a un torneo). No hace falta ir
        # a contarla.
        return self._a_salida(equipo, 0)

    async def update(self, id_: int, data: EquipoUpdate) -> EquipoOut:
        equipo = await self.repo.get_or_404(id_)
        cambios = data.model_dump(exclude_unset=True)

        disciplina_nueva = cambios.get("disciplina_id")
        modalidad_nueva = cambios.get("modalidad_id")
        cambia_disciplina = disciplina_nueva is not None and disciplina_nueva != equipo.disciplina_id

        # EC-38: la disciplina de un equipo YA inscrito no se puede
        # cambiar. Se chequea solo si realmente cambia — un PATCH que
        # reenvía la misma disciplina (lo que hace un formulario de
        # edición completo) no es un cambio y no debe bloquearse.
        if cambia_disciplina and await self.repo.tiene_inscripciones(id_):
            raise DomainRuleError(
                "No se puede cambiar la disciplina de un equipo que ya está inscrito en un torneo. "
                "Cancelá sus inscripciones primero, o creá un equipo nuevo en la otra disciplina."
            )

        if disciplina_nueva is not None or modalidad_nueva is not None:
            await self._validar_disciplina_modalidad(
                disciplina_nueva if disciplina_nueva is not None else equipo.disciplina_id,
                modalidad_nueva if modalidad_nueva is not None else equipo.modalidad_id,
            )

        actualizado = await self.repo.save_changes(equipo, **cambios)
        return await self._con_plantilla(actualizado)

    async def soft_delete(self, id_: int) -> EquipoOut:
        # TASK-016 (FUN-21): dar de baja un equipo que sigue inscripto en un
        # torneo activo lo saca de los listados mientras sus partidos siguen
        # programados. Primero se cancela la inscripción.
        torneos = await self.session.execute(
            select(Torneo.nombre)
            .join(InscripcionTorneo, InscripcionTorneo.torneo_id == Torneo.id)
            .where(
                InscripcionTorneo.equipo_id == id_,
                InscripcionTorneo.estado.in_(("Inscrito", "Confirmado")),
                Torneo.estado == "Activo",
            )
        )
        nombres = [n for n in torneos.scalars().all()]
        if nombres:
            raise ConflictError(
                "El equipo sigue inscripto en torneos activos ("
                + ", ".join(n or "sin nombre" for n in nombres)
                + "). Cancelá esas inscripciones antes de darlo de baja."
            )
        equipo = await self.repo.soft_delete(id_, estado_inactivo="Inactivo")
        return await self._con_plantilla(equipo)

    async def _validar_disciplina_modalidad(self, disciplina_id: int, modalidad_id: int) -> None:
        """D-Eng-15 — doble cinturón, igual que TORNEO: el trigger
        fn_validar_equipo_modalidad (06_triggers.sql) es la red de
        seguridad para un INSERT crudo; este chequeo es el que le da al
        admin un mensaje que se puede leer en pantalla, con los nombres
        reales en vez de un error de Postgres."""
        await self.disciplina_repo.get_or_404(disciplina_id)  # 404 claro si el id no existe
        modalidad = await self.modalidad_repo.get_or_404(modalidad_id)
        if modalidad.disciplina_id != disciplina_id:
            raise DomainRuleError(
                f"La modalidad '{modalidad.nombre}' no pertenece a la disciplina elegida."
            )

    async def _con_plantilla(self, equipo: Equipo) -> EquipoOut:
        totales = await self.repo.plantilla_total_por_equipo([equipo.id])
        return self._a_salida(equipo, totales.get(equipo.id, 0))

    @staticmethod
    def _a_salida(equipo: Equipo, plantilla_total: int) -> EquipoOut:
        salida = EquipoOut.model_validate(equipo)
        salida.plantilla_total = plantilla_total
        return salida

