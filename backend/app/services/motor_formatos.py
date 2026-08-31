"""Motor de Formatos de Competición (Liga, Eliminación, Grupos + Playoffs)
— motor-formatos-plantillas-navegacion-plan.md, requerimiento #4.

Los 3 algoritmos (fixture round robin, sorteo de bracket, cruce de grupos
a playoffs) siguen el diseño de la Fase 3 del plan ("nivel de diseño, no
código de producción"), con el partido de Tercer Lugar incorporado desde
el vamos (confirmado en scope — ver "Decisiones confirmadas" del plan).

Convención de nombres de ronda: se calculan desde la Final hacia atrás
(Final, Semifinal, Cuartos de Final...) — Decisión G1: una sola FASE
Tipo='Eliminacion' para TODO el bracket, el nombre de ronda se denormaliza
en PARTIDOS.Ronda_Nombre en vez de una FASE por ronda.
"""
import math
import random
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.fase import Fase
from app.models.grupo import Grupo
from app.models.grupo_equipo import GrupoEquipo
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.partido import Partido
from app.models.sorteo import Sorteo
from app.models.torneo import Torneo
from app.repositories.estadisticas import EstadisticasRepository
from app.repositories.fase import FaseRepository
from app.repositories.grupo import GrupoRepository
from app.repositories.grupo_equipo import GrupoEquipoRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.torneo import TorneoRepository

_NOMBRES_DESDE_FINAL = [
    "Final",
    "Semifinal",
    "Cuartos de Final",
    "Octavos de Final",
    "Dieciseisavos de Final",
    "Treintaidosavos de Final",
]


def _nombre_ronda(rondas_totales: int, ronda: int) -> str:
    idx = rondas_totales - ronda
    if 0 <= idx < len(_NOMBRES_DESDE_FINAL):
        return _NOMBRES_DESDE_FINAL[idx]
    return f"Ronda {ronda}"


def _siguiente_potencia_de_2(n: int) -> int:
    t = 1
    while t < n:
        t *= 2
    return t


def algoritmo_fixture_liga(equipo_ids: list[int], ida_vuelta: bool) -> list[tuple[int, int, int]]:
    """Método del círculo. Devuelve (local_id, visitante_id, jornada).
    Reutilizado tal cual para el round robin DENTRO de cada grupo (mismo
    algoritmo, EC-57: funciona igual sin importar el tamaño del grupo)."""
    equipos: list[int | None] = list(equipo_ids)
    if len(equipos) % 2 == 1:
        equipos.append(None)  # BYE — descansa 1 por jornada (EC-53)
    n = len(equipos)
    if n < 2:
        return []
    fijo, rotables = equipos[0], equipos[1:]
    partidos: list[tuple[int, int, int]] = []
    for jornada in range(1, n):
        ronda = [fijo] + rotables
        for i in range(n // 2):
            local, visitante = ronda[i], ronda[n - 1 - i]
            if local is not None and visitante is not None:
                partidos.append((local, visitante, jornada))
        rotables = [rotables[-1]] + rotables[:-1]
    if ida_vuelta:
        partidos += [(v, l, j + (n - 1)) for (l, v, j) in partidos]
    return partidos


class MotorFormatosService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.torneo_repo = TorneoRepository(session)
        self.fase_repo = FaseRepository(session)
        self.grupo_repo = GrupoRepository(session)
        self.grupo_equipo_repo = GrupoEquipoRepository(session)
        self.inscripcion_repo = InscripcionTorneoRepository(session)
        self.estadisticas_repo = EstadisticasRepository(session)

    # ---------- helpers compartidos ----------

    async def _inscripciones_activas(self, torneo_id: int) -> list[InscripcionTorneo]:
        todas = await self.inscripcion_repo.list(torneo_id=torneo_id, limit=200)
        return [i for i in todas if i.estado in ("Inscrito", "Confirmado") and i.equipo_id is not None]

    async def _fase_orden1(self, torneo_id: int, tipo_esperado: str) -> Fase:
        fases = await self.fase_repo.listar_por_torneo(torneo_id)
        fase = next((f for f in fases if f.orden == 1), None)
        if fase is None or fase.tipo != tipo_esperado:
            raise DomainRuleError(
                f"Este torneo no tiene una fase de tipo {tipo_esperado} en Orden 1 — revisá su Formato."
            )
        return fase

    async def _partidos_de_fase(self, fase_id: int) -> list[Partido]:
        result = await self.session.execute(select(Partido).where(Partido.fase_id == fase_id))
        return list(result.scalars().all())

    async def _preparar_rehacer_si_corresponde(self, fase: Fase) -> str | None:
        """EC-52: si la fase ya tiene partidos, o se bloquea (alguno
        Finalizado) o se limpia para volver a sortear (ninguno
        Finalizado — borra los PARTIDOS/GRUPO existentes, marca el
        SORTEOS viejo 'Rehecho'). Devuelve la semilla del sorteo viejo, si
        había uno (no se usa, solo se expone por si hace falta auditar)."""
        partidos = await self._partidos_de_fase(fase.id)
        if not partidos:
            return None
        if any(p.estado == "Finalizado" for p in partidos):
            raise DomainRuleError("No se puede rehacer el sorteo: ya hay resultados registrados en esta fase.")

        sorteo_result = await self.session.execute(
            select(Sorteo).where(Sorteo.fase_id == fase.id, Sorteo.estado == "Completado")
        )
        sorteo_viejo = sorteo_result.scalars().first()
        semilla_vieja = sorteo_viejo.semilla if sorteo_viejo else None
        if sorteo_viejo is not None:
            sorteo_viejo.estado = "Rehecho"

        for p in partidos:
            await self.session.delete(p)
        grupos = await self.grupo_repo.listar_por_fase(fase.id)
        for g in grupos:
            await self.session.delete(g)  # ON DELETE CASCADE se lleva su GRUPO_EQUIPO
        await self.session.flush()
        return semilla_vieja

    # ---------- Generar Fixture (Liga) ----------

    async def generar_fixture(self, torneo_id: int) -> Fase:
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        if torneo.formato != "Liga":
            raise DomainRuleError("Generar Fixture es solo para torneos de Formato Liga.")
        fase = await self._fase_orden1(torneo_id, "Liga")
        if await self._partidos_de_fase(fase.id):
            raise DomainRuleError("Esta fase ya tiene un fixture generado.")

        inscripciones = await self._inscripciones_activas(torneo_id)
        if len(inscripciones) < 2:
            raise DomainRuleError("Hacen falta al menos 2 equipos matriculados para generar el fixture.")

        equipo_ids = [i.equipo_id for i in inscripciones]
        partidos = algoritmo_fixture_liga(equipo_ids, torneo.ida_vuelta)
        fecha_base = datetime.combine(torneo.fecha_inicio, datetime.min.time())
        for local_id, visitante_id, jornada in partidos:
            self.session.add(
                Partido(
                    torneo_id=torneo_id,
                    equipos_id_local=local_id,
                    equipos_id_visitante=visitante_id,
                    fecha_partido=fecha_base + timedelta(days=7 * (jornada - 1)),
                    jornada=jornada,
                    fase_id=fase.id,
                    estado="Programado",
                )
            )
        fase.estado = "En_Curso"
        await self.session.commit()
        await self.session.refresh(fase)
        return fase

    # ---------- Sorteo (Eliminación directa, o asignación de Grupos) ----------

    async def sortear(self, torneo_id: int, usuario_id: int, semilla: str | None = None) -> Fase:
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        if torneo.formato == "Eliminacion":
            fase = await self._fase_orden1(torneo_id, "Eliminacion")
            await self._preparar_rehacer_si_corresponde(fase)
            inscripciones = await self._inscripciones_activas(torneo_id)
            equipo_ids = [i.equipo_id for i in inscripciones]
            await self._sortear_bracket(torneo, fase, usuario_id, semilla, equipo_ids, barajar=True)
        elif torneo.formato == "Grupos_Playoffs":
            fase = await self._fase_orden1(torneo_id, "Grupos")
            await self._preparar_rehacer_si_corresponde(fase)
            await self._sortear_grupos(torneo, fase, usuario_id, semilla)
        else:
            raise DomainRuleError("Hacer Sorteo es solo para torneos de Eliminación o de Grupos + Playoffs.")
        await self.session.commit()
        await self.session.refresh(fase)
        return fase

    async def _sortear_grupos(self, torneo: Torneo, fase: Fase, usuario_id: int, semilla: str | None) -> None:
        inscripciones = await self._inscripciones_activas(torneo.id)
        if len(inscripciones) < 2:
            raise DomainRuleError("Hacen falta al menos 2 equipos matriculados para sortear los grupos.")

        equipos_por_grupo = torneo.equipos_por_grupo or 4
        num_grupos = max(1, math.ceil(len(inscripciones) / equipos_por_grupo))
        rng = random.Random(semilla)
        barajadas = list(inscripciones)
        rng.shuffle(barajadas)
        # EC-57: reparto lo más parejo posible (±1 equipo entre grupos) —
        # round robin de asignación, no bloques consecutivos.
        miembros_por_grupo: list[list[InscripcionTorneo]] = [[] for _ in range(num_grupos)]
        for i, insc in enumerate(barajadas):
            miembros_por_grupo[i % num_grupos].append(insc)

        letras = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        fecha_base = datetime.combine(torneo.fecha_inicio, datetime.min.time())
        for idx, miembros in enumerate(miembros_por_grupo):
            grupo = Grupo(fase_id=fase.id, nombre=letras[idx] if idx < len(letras) else str(idx + 1))
            self.session.add(grupo)
            await self.session.flush()
            for insc in miembros:
                self.session.add(GrupoEquipo(grupo_id=grupo.id, inscripcion_torneo_id=insc.id))
            await self.session.flush()  # dispara fn_validar_equipo_un_grupo_por_fase

            pares = algoritmo_fixture_liga([m.equipo_id for m in miembros], ida_vuelta=False)
            for local_id, visitante_id, jornada in pares:
                self.session.add(
                    Partido(
                        torneo_id=torneo.id,
                        equipos_id_local=local_id,
                        equipos_id_visitante=visitante_id,
                        fecha_partido=fecha_base + timedelta(days=7 * (jornada - 1)),
                        jornada=jornada,
                        fase_id=fase.id,
                        grupo_id=grupo.id,
                        estado="Programado",
                    )
                )
        fase.estado = "En_Curso"
        self.session.add(Sorteo(fase_id=fase.id, realizado_por=usuario_id, semilla=semilla, estado="Completado"))

    async def _crear_shell(self, torneo: Torneo, fase: Fase, ronda_nombre: str, fecha_base: datetime) -> Partido:
        p = Partido(
            torneo_id=torneo.id,
            fase_id=fase.id,
            ronda_nombre=ronda_nombre,
            fecha_partido=fecha_base,
            estado="Programado",
        )
        self.session.add(p)
        await self.session.flush()
        return p

    async def _sortear_bracket(
        self,
        torneo: Torneo,
        fase: Fase,
        usuario_id: int,
        semilla: str | None,
        equipo_ids: list[int],
        barajar: bool,
    ) -> None:
        """EC-49 (byes): los primeros `byes` equipos del sorteo avanzan
        directo a ronda 2, sin jugar ronda 1. Partido por el 3er/4to lugar
        (confirmado en scope): se engancha a las 2 semifinales REALES —
        si una "semifinal" terminó siendo un bye directo (posible solo en
        un bracket de 4 con 3 equipos, tamano==4), ese lado del Tercer
        Lugar queda sin completar automáticamente; caso borde no cubierto
        por el plan, documentado acá en vez de silencioso."""
        n = len(equipo_ids)
        if n < 2:
            raise DomainRuleError("Hacen falta al menos 2 equipos matriculados para sortear el bracket.")

        ids = list(equipo_ids)
        if barajar:
            random.Random(semilla).shuffle(ids)
        # EC-50: el cruce de grupos a playoffs ya viene ordenado (1°A,
        # 2°B, 1°B, 2°A...) — no se vuelve a barajar.

        tamano = _siguiente_potencia_de_2(n)
        rondas = int(math.log2(tamano))
        byes_n = tamano - n
        con_bye, sin_bye = ids[:byes_n], ids[byes_n:]
        fecha_base = datetime.combine(torneo.fecha_inicio, datetime.min.time())

        if rondas <= 1:
            # n == 2 (tamano == 2): la Final ES el único partido — ambos
            # equipos ya se conocen, sin shells ni Tercer Lugar (EC-58,
            # tamano < 4).
            self.session.add(
                Partido(
                    torneo_id=torneo.id,
                    fase_id=fase.id,
                    ronda_nombre="Final",
                    equipos_id_local=sin_bye[0],
                    equipos_id_visitante=sin_bye[1],
                    fecha_partido=fecha_base,
                    estado="Programado",
                )
            )
            fase.estado = "En_Curso"
            self.session.add(
                Sorteo(fase_id=fase.id, realizado_por=usuario_id, semilla=semilla, estado="Completado")
            )
            return

        final = await self._crear_shell(torneo, fase, _nombre_ronda(rondas, rondas), fecha_base)

        semifinales_reales: list[Partido] | None = None
        if rondas == 2:
            productores: list[tuple[Partido, str]] = [(final, "Local"), (final, "Visitante")]
        else:
            nivel = [final]
            for r in range(rondas - 1, 1, -1):
                siguiente_nivel: list[Partido] = []
                for padre in nivel:
                    for slot in ("Local", "Visitante"):
                        nodo = await self._crear_shell(torneo, fase, _nombre_ronda(rondas, r), fecha_base)
                        nodo.partido_siguiente_id = padre.id
                        nodo.slot_siguiente = slot
                        siguiente_nivel.append(nodo)
                if r == rondas - 1:
                    semifinales_reales = list(siguiente_nivel)
                nivel = siguiente_nivel
            productores = [(p, slot) for p in nivel for slot in ("Local", "Visitante")]

        con_bye_iter = iter(con_bye)
        sin_bye_iter = iter(sin_bye)
        ronda1_reales: list[Partido] = []
        nombre_r1 = _nombre_ronda(rondas, 1)
        for padre, slot in productores:
            equipo_bye = next(con_bye_iter, None)
            if equipo_bye is not None:
                if slot == "Local":
                    padre.equipos_id_local = equipo_bye
                else:
                    padre.equipos_id_visitante = equipo_bye
            else:
                local = next(sin_bye_iter)
                visitante = next(sin_bye_iter)
                p1 = Partido(
                    torneo_id=torneo.id,
                    fase_id=fase.id,
                    ronda_nombre=nombre_r1,
                    equipos_id_local=local,
                    equipos_id_visitante=visitante,
                    partido_siguiente_id=padre.id,
                    slot_siguiente=slot,
                    fecha_partido=fecha_base,
                    estado="Programado",
                )
                self.session.add(p1)
                await self.session.flush()
                ronda1_reales.append(p1)

        if torneo.incluye_tercer_lugar and tamano >= 4:
            tercer_lugar = await self._crear_shell(torneo, fase, "Tercer Lugar", fecha_base)
            semis = semifinales_reales if semifinales_reales is not None else ronda1_reales
            for i, semi in enumerate(semis[:2]):
                semi.partido_perdedor_siguiente_id = tercer_lugar.id
                semi.slot_perdedor_siguiente = "Local" if i == 0 else "Visitante"

        fase.estado = "En_Curso"
        self.session.add(Sorteo(fase_id=fase.id, realizado_por=usuario_id, semilla=semilla, estado="Completado"))

    # ---------- Generar Playoffs (cruce desde Grupos) ----------

    def _cruzar_grupos(self, clasificados: dict[str, list[int]]) -> list[int]:
        """EC-50: cruce fijo (1°A-2°B, 1°B-2°A, 1°C-2°D...), no un nuevo
        sorteo — minimiza el riesgo de repetir en primera ronda un cruce
        ya jugado en la fase de grupos. Con un número impar de grupos, el
        último queda sin pareja de cruce y entra en orden de tabla
        (detalle de implementación sin impacto de diseño, según el plan)."""
        nombres = sorted(clasificados.keys())
        cruce: list[int] = []
        i = 0
        while i + 1 < len(nombres):
            clas_a, clas_b = clasificados[nombres[i]], clasificados[nombres[i + 1]]
            n = min(len(clas_a), len(clas_b))
            if n >= 2:
                cruce += [clas_a[0], clas_b[1], clas_b[0], clas_a[1]]
                for puesto in range(2, n):
                    cruce += [clas_a[puesto], clas_b[puesto]]
            elif n == 1:
                cruce += [clas_a[0], clas_b[0]]
            i += 2
        if i < len(nombres):
            cruce += clasificados[nombres[i]]
        return cruce

    async def generar_playoffs(self, torneo_id: int, usuario_id: int) -> Fase:
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        if torneo.formato != "Grupos_Playoffs":
            raise DomainRuleError("Generar Playoffs es solo para torneos de Formato Grupos + Playoffs.")
        fase_grupos = await self._fase_orden1(torneo_id, "Grupos")

        partidos_grupos = await self._partidos_de_fase(fase_grupos.id)
        if not partidos_grupos:
            raise DomainRuleError("Todavía no se sortearon los grupos de este torneo.")
        if any(p.estado not in ("Finalizado", "Cancelado") for p in partidos_grupos):
            raise DomainRuleError("La Fase de Grupos todavía tiene partidos sin terminar.")
        fase_grupos.estado = "Finalizada"  # se computa acá, recién al confirmarse (no hay trigger que la mantenga en vivo)

        grupos = await self.grupo_repo.listar_por_fase(fase_grupos.id)
        clasificados_por_grupo = torneo.clasificados_por_grupo or 2
        clasificados: dict[str, list[int]] = {}
        for g in grupos:
            tabla = await self.estadisticas_repo.tabla_posiciones(torneo_id, grupo_id=g.id)
            clasificados[g.nombre] = [fila["equipo_id"] for fila in tabla[:clasificados_por_grupo]]

        cruce = self._cruzar_grupos(clasificados)
        nueva_fase = Fase(
            torneo_id=torneo_id,
            nombre="Eliminatoria",
            tipo="Eliminacion",
            orden=fase_grupos.orden + 1,
            estado="Pendiente",
        )
        self.session.add(nueva_fase)
        await self.session.flush()

        await self._sortear_bracket(torneo, nueva_fase, usuario_id, semilla=None, equipo_ids=cruce, barajar=False)
        await self.session.commit()
        await self.session.refresh(nueva_fase)
        return nueva_fase

    # ---------- Vista de bracket (lectura) ----------

    async def bracket(self, torneo_id: int) -> list[Partido]:
        """PARTIDOS directo (no vw_resultados_partidos): un shell con
        equipos NULL desaparecería de esa vista (INNER JOIN contra
        EQUIPOS) — acá el frontend necesita verlo igual para pintar
        "Ganador Partido N"."""
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        if torneo.formato == "Liga":
            raise DomainRuleError("Un torneo de Formato Liga no tiene bracket.")
        fase = await self.fase_repo.ultima_por_torneo(torneo_id)
        if fase is None or fase.tipo != "Eliminacion":
            return []
        return await self._partidos_de_fase(fase.id)
