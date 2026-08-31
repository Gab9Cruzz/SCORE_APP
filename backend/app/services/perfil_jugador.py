"""Perfil de Jugador: stats + trayectoria consolidadas por disciplina
(equipos-jugadores-plan.md, Fase 2, Etapa D)."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.disciplina import DisciplinaRepository
from app.repositories.equipo import EquipoRepository
from app.repositories.estadisticas import EstadisticasRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador import JugadorRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.repositories.jugador_perfil_disciplina import JugadorPerfilDisciplinaRepository
from app.repositories.torneo import TorneoRepository
from app.repositories.traspaso import TraspasoRepository
from app.schemas.perfil_jugador import (
    EquipoActivoOut,
    PerfilDisciplinaOut,
    PerfilJugadorOut,
    TraspasoTrayectoriaOut,
)


class PerfilJugadorService:
    def __init__(self, session: AsyncSession):
        self.jugador_repo = JugadorRepository(session)
        self.perfil_repo = JugadorPerfilDisciplinaRepository(session)
        self.disciplina_repo = DisciplinaRepository(session)
        self.jugador_equipo_repo = JugadorEquipoRepository(session)
        self.inscripcion_repo = InscripcionTorneoRepository(session)
        self.equipo_repo = EquipoRepository(session)
        self.torneo_repo = TorneoRepository(session)
        self.traspaso_repo = TraspasoRepository(session)
        self.estadisticas_repo = EstadisticasRepository(session)

    async def _etiqueta_inscripcion(self, inscripcion_torneo_id: int | None) -> str | None:
        if inscripcion_torneo_id is None:
            return None
        inscripcion = await self.inscripcion_repo.get_or_404(inscripcion_torneo_id)
        torneo = await self.torneo_repo.get_or_404(inscripcion.torneo_id)
        equipo = await self.equipo_repo.get_or_404(inscripcion.equipo_id)
        return f"{torneo.nombre} — {equipo.nombre}"

    async def obtener(self, jugador_id: int) -> PerfilJugadorOut:
        jugador = await self.jugador_repo.get_or_404(jugador_id)
        perfiles = await self.perfil_repo.list(jugador_id=jugador_id, limit=200)

        disciplinas_out: list[PerfilDisciplinaOut] = []
        for perfil in perfiles:
            disciplina = await self.disciplina_repo.get_or_404(perfil.disciplina_id)
            estado = await self.estadisticas_repo.estado_perfil(perfil.id)
            goles_totales = await self.estadisticas_repo.goles_totales_perfil(perfil.id)

            equipos_activos: list[EquipoActivoOut] = []
            for membresia in await self.jugador_equipo_repo.listar_activos_por_perfil(perfil.id):
                inscripcion = await self.inscripcion_repo.get_or_404(membresia.inscripcion_torneo_id)
                torneo = await self.torneo_repo.get_or_404(inscripcion.torneo_id)
                equipo = await self.equipo_repo.get_or_404(inscripcion.equipo_id)
                equipos_activos.append(
                    EquipoActivoOut(
                        inscripcion_torneo_id=inscripcion.id,
                        torneo_id=torneo.id,
                        torneo=torneo.nombre,
                        equipo_id=equipo.id,
                        equipo=equipo.nombre,
                        dorsal=membresia.dorsal,
                        fecha_inicio=membresia.fecha_inicio,
                    )
                )

            trayectoria: list[TraspasoTrayectoriaOut] = []
            traspasos = await self.traspaso_repo.list(jugador_perfil_id=perfil.id, limit=200)
            for t in sorted(traspasos, key=lambda x: x.fecha_traspaso):
                # Inscripcion_Destino_ID es NOT NULL (01_schema.sql) — a
                # diferencia de origen, siempre resuelve a un string real.
                destino = await self._etiqueta_inscripcion(t.inscripcion_destino_id)
                assert destino is not None
                trayectoria.append(
                    TraspasoTrayectoriaOut(
                        id=t.id,
                        fecha_traspaso=t.fecha_traspaso,
                        origen=await self._etiqueta_inscripcion(t.inscripcion_origen_id),
                        destino=destino,
                        motivo=t.motivo,
                        estado=t.estado,
                    )
                )

            disciplinas_out.append(
                PerfilDisciplinaOut(
                    jugador_perfil_id=perfil.id,
                    disciplina_id=disciplina.id,
                    disciplina=disciplina.nombre,
                    estado=estado or "Libre",
                    goles_totales=goles_totales,
                    equipos_activos=equipos_activos,
                    trayectoria=trayectoria,
                )
            )

        return PerfilJugadorOut(
            jugador_id=jugador.id,
            nombre=jugador.nombre,
            foto_url=jugador.foto_url,
            cedula=jugador.cedula,
            correo_electronico=jugador.correo_electronico,
            disciplinas=disciplinas_out,
        )
