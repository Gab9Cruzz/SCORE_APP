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

Cierre de Fase Regular + Llaves + Playoffs
(docs/plans/cierre-fase-regular-llaves-playoffs-plan.md): el bracket ahora
puede tener llaves a DOS partidos (Ida/Vuelta) según
`Torneo.Formato_Eliminatoria` — `_crear_llave` decide 1 o 2 partidos por
cruce; la resolución del agregado vive en SQL (`fn_resolver_llave`,
06_triggers.sql), reusada acá vía una consulta directa en vez de
reimplementar la misma regla en Python (DRY — una sola fuente de verdad
para "quién ganó esta llave")."""
import logging
import math
import random
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
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

logger = logging.getLogger(__name__)

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


def _piernas_por_ronda(formato_eliminatoria: str, es_final: bool) -> int:
    """C1 del plan: cuántos partidos tiene UNA llave de esta ronda.
    'Unico' → siempre 1. 'Ida_Vuelta' → siempre 2, Final incluida.
    'Mixto' → 2 en todas las rondas MENOS la Final (1). El Tercer Lugar
    nunca llama a esto — siempre se crea con 'Unico' a mano (ver
    _sortear_bracket): no es una ronda del bracket, es un partido de
    consolación, ninguna competencia real lo juega a doble partido."""
    if formato_eliminatoria == "Unico":
        return 1
    if formato_eliminatoria == "Ida_Vuelta":
        return 2
    if formato_eliminatoria == "Mixto":
        return 1 if es_final else 2
    raise DomainRuleError(f"Formato de eliminatoria desconocido: {formato_eliminatoria}.")


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
        había uno (no se usa, solo se expone por si hace falta auditar).

        B5 (cierre-fase-regular-llaves-playoffs-plan.md, Finding 8): el
        borrado no necesita ORDEN especial pese a la FK autorreferencial
        nueva (Partido_Ida_ID) — esa FK es `ON DELETE SET NULL`, mismo
        patrón que Partido_Siguiente_ID/Partido_Perdedor_Siguiente_ID de
        siempre, así que Postgres resuelve cualquier orden de borrado
        dentro de esta misma transacción sin violar la FK."""
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
            await self._sortear_bracket(
                torneo, fase, usuario_id, semilla, equipo_ids, barajar=True,
                formato_eliminatoria=torneo.formato_eliminatoria,
            )
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

            # A4 (Finding: requerimiento #3 del plan) — la fase de grupos
            # ahora puede jugarse a ida y vuelta: se reusa Torneo.Ida_Vuelta
            # (ya existe, antes prohibido acá) con el significado "round
            # robin doble DENTRO de cada grupo" en vez de agregar una
            # segunda columna con semántica idéntica.
            pares = algoritmo_fixture_liga([m.equipo_id for m in miembros], ida_vuelta=torneo.ida_vuelta)
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

    async def _crear_llave(
        self,
        torneo: Torneo,
        fase: Fase,
        ronda_nombre: str,
        formato_eliminatoria: str,
        es_final: bool,
        fecha_ida: datetime,
        fecha_vuelta: datetime,
        padre: Partido | None,
        slot: str | None,
        equipo_local: int | None = None,
        equipo_visitante: int | None = None,
    ) -> Partido:
        """T10/Finding 13 (extraído de `_sortear_bracket` para que ese
        método mantenga un branch por CONCEPTO, no uno por combinación de
        formato×ronda): crea 1 o 2 partidos para un cruce/slot del bracket
        y devuelve el partido CANÓNICO — la VUELTA si son 2 piernas, el
        único si es 1 — que es el que los llamadores usan como `padre`
        para el próximo nivel de encadenamiento, y el que carga
        Partido_Siguiente_ID/Slot_Siguiente hacia el `padre` recibido acá.

        `equipo_local`/`equipo_visitante` en None (el caso normal para
        rondas 2+): nace como shell, el trigger de propagación completa
        los equipos cuando el partido anterior del bracket termina —
        `fn_propagar_ganador_bracket` ya sabe completar TAMBIÉN la ida de
        una llave destino (slot invertido) desde un solo feeder, así que
        no hace falta ninguna lógica extra acá para ese caso."""
        piernas = _piernas_por_ronda(formato_eliminatoria, es_final)

        if piernas == 1:
            p = Partido(
                torneo_id=torneo.id,
                fase_id=fase.id,
                ronda_nombre=ronda_nombre,
                equipos_id_local=equipo_local,
                equipos_id_visitante=equipo_visitante,
                fecha_partido=fecha_ida,
                estado="Programado",
            )
            if padre is not None:
                p.partido_siguiente_id = padre.id
                p.slot_siguiente = slot
            self.session.add(p)
            await self.session.flush()
            return p

        # Localía: la IDA la juega de local el primer equipo del cruce; la
        # VUELTA invierte (el que cierra de local es el mejor sembrado).
        ida = Partido(
            torneo_id=torneo.id,
            fase_id=fase.id,
            ronda_nombre=ronda_nombre,
            equipos_id_local=equipo_local,
            equipos_id_visitante=equipo_visitante,
            fecha_partido=fecha_ida,
            estado="Programado",
        )
        self.session.add(ida)
        await self.session.flush()

        vuelta = Partido(
            torneo_id=torneo.id,
            fase_id=fase.id,
            ronda_nombre=ronda_nombre,
            equipos_id_local=equipo_visitante,
            equipos_id_visitante=equipo_local,
            fecha_partido=fecha_vuelta,
            partido_ida_id=ida.id,
            estado="Programado",
        )
        if padre is not None:
            vuelta.partido_siguiente_id = padre.id
            vuelta.slot_siguiente = slot
        self.session.add(vuelta)
        await self.session.flush()
        return vuelta

    async def _sortear_bracket(
        self,
        torneo: Torneo,
        fase: Fase,
        usuario_id: int,
        semilla: str | None,
        equipo_ids: list[int],
        barajar: bool,
        formato_eliminatoria: str | None = None,
        seeds: list[int] | None = None,
    ) -> None:
        """EC-49 (byes): los primeros `byes` equipos SEMBRADOS avanzan
        directo a ronda 2, sin jugar ronda 1. Partido por el 3er/4to lugar
        (confirmado en scope): se engancha a las 2 semifinales REALES —
        si una "semifinal" terminó siendo un bye directo (posible solo en
        un bracket de 4 con 3 equipos, tamano==4), ese lado del Tercer
        Lugar queda sin completar automáticamente; caso borde no cubierto
        por el plan, documentado acá en vez de silencioso.

        `seeds` (Finding 6 del review): orden de MEJOR A PEOR sembrado,
        separado de `equipo_ids` (el orden de CRUCE/emparejamiento, que
        evita repetir en primera ronda un cruce ya jugado en grupos —
        `_cruzar_grupos`/`_cruzar_tabla_unica`). Antes los byes salían de
        `equipo_ids[:byes_n]`, que con un cruce entrelazado tipo
        `[1, N, 2, N-1...]` le daba un bye al PEOR clasificado (seed N)
        junto al mejor. Con `barajar=True` (sorteo aleatorio, sin ranking
        real) `seeds` se deriva del propio orden post-shuffle — mismo
        comportamiento de siempre para un sorteo genuinamente al azar.

        T16 — forma de dos piernas (Cierre de Fase Regular + Llaves +
        Playoffs): cada cruce de rondas 2+ ya no es un shell, es una
        LLAVE (`_crear_llave`) de 1 o 2 partidos según
        `formato_eliminatoria` — 'Unico' siempre 1; 'Ida_Vuelta' siempre
        2, Final incluida; 'Mixto' 2 en todo menos la Final. Un bye
        SIGUE sin jugar ida ni vuelta (se sienta directo en las dos
        piernas del padre, si el padre es una llave — ver el bloque
        `con_bye_iter` más abajo). El Tercer Lugar es SIEMPRE partido
        único en los tres formatos, nunca una llave — no es una ronda del
        bracket, es un partido de consolación."""
        n = len(equipo_ids)
        if n < 2:
            raise DomainRuleError("Hacen falta al menos 2 equipos matriculados para sortear el bracket.")

        formato = formato_eliminatoria or torneo.formato_eliminatoria or "Unico"

        ids = list(equipo_ids)
        if barajar:
            random.Random(semilla).shuffle(ids)
            seeds = list(ids)
        elif seeds is None:
            seeds = list(ids)
        # EC-50: el cruce de grupos/liga a playoffs ya viene ordenado — no
        # se vuelve a barajar.

        tamano = _siguiente_potencia_de_2(n)
        rondas = int(math.log2(tamano))
        byes_n = tamano - n
        con_bye = seeds[:byes_n]
        bye_set = set(con_bye)
        sin_bye = [x for x in ids if x not in bye_set]
        fecha_base = datetime.combine(torneo.fecha_inicio, datetime.min.time())

        # Bracket date spacing (CEO review, supera el "+7 dias" de la
        # redacción original): la ronda R cae en fecha_base + 7*R días; la
        # vuelta de esa ronda, 3 días después de su ida.
        def fechas_de_ronda(ronda: int) -> tuple[datetime, datetime]:
            ida = fecha_base + timedelta(days=7 * ronda)
            return ida, ida + timedelta(days=3)

        if rondas <= 1:
            # n == 2 (tamano == 2): la Final ES el único cruce — ambos
            # equipos ya se conocen, sin shells ni Tercer Lugar (EC-58,
            # tamano < 4). Bajo Ida_Vuelta son 2 partidos; bajo Mixto y
            # Unico, 1 (C1 del plan).
            fecha_ida, fecha_vuelta = fechas_de_ronda(1)
            await self._crear_llave(
                torneo, fase, "Final", formato, es_final=True,
                fecha_ida=fecha_ida, fecha_vuelta=fecha_vuelta,
                padre=None, slot=None,
                equipo_local=sin_bye[0], equipo_visitante=sin_bye[1],
            )
            fase.estado = "En_Curso"
            self.session.add(
                Sorteo(fase_id=fase.id, realizado_por=usuario_id, semilla=semilla, estado="Completado")
            )
            return

        fecha_ida_final, fecha_vuelta_final = fechas_de_ronda(rondas)
        final = await self._crear_llave(
            torneo, fase, _nombre_ronda(rondas, rondas), formato, es_final=True,
            fecha_ida=fecha_ida_final, fecha_vuelta=fecha_vuelta_final,
            padre=None, slot=None,
        )

        semifinales_reales: list[Partido] | None = None
        if rondas == 2:
            productores: list[tuple[Partido, str]] = [(final, "Local"), (final, "Visitante")]
        else:
            nivel = [final]
            for r in range(rondas - 1, 1, -1):
                fecha_ida_r, fecha_vuelta_r = fechas_de_ronda(r)
                siguiente_nivel: list[Partido] = []
                for padre in nivel:
                    for slot in ("Local", "Visitante"):
                        nodo = await self._crear_llave(
                            torneo, fase, _nombre_ronda(rondas, r), formato, es_final=False,
                            fecha_ida=fecha_ida_r, fecha_vuelta=fecha_vuelta_r,
                            padre=padre, slot=slot,
                        )
                        siguiente_nivel.append(nodo)
                if r == rondas - 1:
                    semifinales_reales = list(siguiente_nivel)
                nivel = siguiente_nivel
            productores = [(p, slot) for p in nivel for slot in ("Local", "Visitante")]

        con_bye_iter = iter(con_bye)
        sin_bye_iter = iter(sin_bye)
        ronda1_reales: list[Partido] = []
        nombre_r1 = _nombre_ronda(rondas, 1)
        fecha_ida_r1, fecha_vuelta_r1 = fechas_de_ronda(1)
        for padre, slot in productores:
            equipo_bye = next(con_bye_iter, None)
            if equipo_bye is not None:
                if slot == "Local":
                    padre.equipos_id_local = equipo_bye
                else:
                    padre.equipos_id_visitante = equipo_bye
                # Si `padre` es una llave a dos partidos, el mismo equipo
                # tiene que quedar sentado TAMBIÉN en la ida (slot
                # invertido) — un bye no juega ida ni vuelta (sin cambios),
                # pero fn_resolver_llave necesita las DOS piernas con los
                # equipos ya puestos para calcular el agregado apenas la
                # otra semifinal termine.
                if padre.partido_ida_id is not None:
                    ida = await self.session.get(Partido, padre.partido_ida_id)
                    if slot == "Local":
                        ida.equipos_id_visitante = equipo_bye
                    else:
                        ida.equipos_id_local = equipo_bye
            else:
                local = next(sin_bye_iter)
                visitante = next(sin_bye_iter)
                p1 = await self._crear_llave(
                    torneo, fase, nombre_r1, formato, es_final=False,
                    fecha_ida=fecha_ida_r1, fecha_vuelta=fecha_vuelta_r1,
                    padre=padre, slot=slot,
                    equipo_local=local, equipo_visitante=visitante,
                )
                ronda1_reales.append(p1)

        if torneo.incluye_tercer_lugar and tamano >= 4:
            # Tercer Lugar: SIEMPRE partido único, en los 3 formatos — no
            # es una ronda del bracket, es un partido de consolación;
            # ninguna competencia real lo juega a doble partido.
            tercer_lugar = await self._crear_llave(
                torneo, fase, "Tercer Lugar", "Unico", es_final=True,
                fecha_ida=fecha_ida_final, fecha_vuelta=fecha_vuelta_final,
                padre=None, slot=None,
            )
            semis = semifinales_reales if semifinales_reales is not None else ronda1_reales
            for i, semi in enumerate(semis[:2]):
                # `semi` ya es el nodo CANÓNICO de esa semifinal (la vuelta
                # si es una llave a dos partidos) — encadenar acá alcanza
                # para que el perdedor de la llave completa llegue al
                # Tercer Lugar.
                semi.partido_perdedor_siguiente_id = tercer_lugar.id
                semi.slot_perdedor_siguiente = "Local" if i == 0 else "Visitante"

        fase.estado = "En_Curso"
        self.session.add(Sorteo(fase_id=fase.id, realizado_por=usuario_id, semilla=semilla, estado="Completado"))

    # ---------- Generar Playoffs (cruce desde Grupos, o desde Liga) ----------

    def _cruzar_grupos(self, clasificados: dict[str, list[int]]) -> tuple[list[int], list[int]]:
        """EC-50: cruce fijo (1°A-2°B, 1°B-2°A, 1°C-2°D...), no un nuevo
        sorteo — minimiza el riesgo de repetir en primera ronda un cruce
        ya jugado en la fase de grupos. Con un número impar de grupos, el
        último queda sin pareja de cruce y entra en orden de tabla
        (detalle de implementación sin impacto de diseño, según el plan).

        Devuelve `(cruce, seeds)` — `seeds` (Finding 6) es el orden de
        sembrado real para asignar byes: todos los 1° puesto (en orden de
        grupo), después todos los 2°, después todos los 3°... Antes los
        byes salían del propio `cruce` (entrelazado), lo que le daba un
        bye al PEOR clasificado del cruce junto al mejor."""
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

        max_puesto = max((len(v) for v in clasificados.values()), default=0)
        seeds: list[int] = []
        for puesto in range(max_puesto):
            for nombre in nombres:
                equipos_grupo = clasificados[nombre]
                if puesto < len(equipos_grupo):
                    seeds.append(equipos_grupo[puesto])
        return cruce, seeds

    def _cruzar_tabla_unica(self, equipo_ids: list[int]) -> tuple[list[int], list[int]]:
        """C2 del plan — nuevo: siembra estándar sobre la tabla única de
        una Liga (ya ordenada mejor a peor): 1 vs N, 2 vs N-1, 3 vs N-2...
        `_cruzar_grupos` no aplica acá (no hay grupos que cruzar). Devuelve
        `(cruce, seeds)` igual que `_cruzar_grupos` — acá `seeds` es
        directamente la tabla, que ya es el orden de sembrado real."""
        n = len(equipo_ids)
        cruce: list[int] = []
        i, j = 0, n - 1
        while i < j:
            cruce += [equipo_ids[i], equipo_ids[j]]
            i += 1
            j -= 1
        if i == j:
            cruce.append(equipo_ids[i])
        return cruce, list(equipo_ids)

    async def generar_playoffs(
        self,
        torneo_id: int,
        usuario_id: int,
        clasificados_por_grupo: int | None = None,
        formato_eliminatoria: str | None = None,
    ) -> Fase:
        """`clasificados_por_grupo` (control-mesa-reactividad-playoffs-
        plan.md, Fase 3 §6): override puntual pedido al momento de generar
        — si se manda, se PERSISTE en `Torneo.clasificados_por_grupo` (Gate
        Final T2: persistir, no efímero), así la próxima generación de este
        torneo ya no vuelve a preguntar salvo que el operador lo cambie de
        nuevo. Si no se manda (None), usa el config existente del torneo
        sin tocarlo — mismo comportamiento que antes de este cambio.
        `formato_eliminatoria` (Fase D del plan) sigue el mismo criterio
        exacto.

        C2 (cierre-fase-regular-llaves-playoffs-plan.md): generalizado a
        Liga → liguilla, reusando `clasificados_por_grupo` con el
        significado "cuántos de la tabla pasan a la liguilla" (Taste
        Decision T3 — una sola columna en vez de dos con semántica
        idéntica)."""
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        if torneo.formato not in ("Grupos_Playoffs", "Liga"):
            raise DomainRuleError(
                "Generar Playoffs es solo para torneos de Formato Grupos + Playoffs, o Liga (liguilla)."
            )
        if clasificados_por_grupo is not None and clasificados_por_grupo < 1:
            raise DomainRuleError("Deben clasificar al menos 1 equipo.")

        fase_regular = await self._fase_orden1(
            torneo_id, "Grupos" if torneo.formato == "Grupos_Playoffs" else "Liga"
        )
        partidos_regular = await self._partidos_de_fase(fase_regular.id)
        if not partidos_regular:
            raise DomainRuleError("Todavía no se generó el fixture/sorteo de este torneo.")
        if any(p.estado not in ("Finalizado", "Cancelado") for p in partidos_regular):
            raise DomainRuleError("La fase regular todavía tiene partidos sin terminar.")
        # Se computa acá, recién al confirmarse (no hay trigger que la mantenga en vivo).
        fase_regular.estado = "Finalizada"

        if clasificados_por_grupo is not None:
            torneo.clasificados_por_grupo = clasificados_por_grupo
        if formato_eliminatoria is not None:
            torneo.formato_eliminatoria = formato_eliminatoria

        if torneo.formato == "Grupos_Playoffs":
            grupos = await self.grupo_repo.listar_por_fase(fase_regular.id)
            n_clasificados = clasificados_por_grupo if clasificados_por_grupo is not None else (torneo.clasificados_por_grupo or 2)
            clasificados: dict[str, list[int]] = {}
            for g in grupos:
                tabla = await self.estadisticas_repo.tabla_posiciones(torneo_id, grupo_id=g.id)
                if len(tabla) < n_clasificados:
                    # Finding 9: un grupo con partidos cancelados (o sin
                    # ninguno jugado) deja menos filas en la tabla de las
                    # que hacen falta clasificar — sin este chequeo, el
                    # cruce arma un bracket corto en silencio.
                    raise DomainRuleError(
                        f"El grupo {g.nombre} tiene {len(tabla)} equipo(s) con partidos jugados — hacen falta "
                        f"{n_clasificados} para clasificar."
                    )
                clasificados[g.nombre] = [fila["equipo_id"] for fila in tabla[:n_clasificados]]
            cruce, seeds = self._cruzar_grupos(clasificados)
        else:  # Liga
            tabla = await self.estadisticas_repo.tabla_posiciones(torneo_id)
            n_clasificados = clasificados_por_grupo if clasificados_por_grupo is not None else (torneo.clasificados_por_grupo or 4)
            if n_clasificados < 2:
                raise DomainRuleError("Hacen falta al menos 2 equipos clasificados para armar la liguilla.")
            if len(tabla) < n_clasificados:
                raise DomainRuleError(
                    f"La tabla tiene {len(tabla)} equipo(s) con partidos jugados — hacen falta "
                    f"{n_clasificados} para armar la liguilla."
                )
            if n_clasificados < len(tabla):
                corte, siguiente = tabla[n_clasificados - 1], tabla[n_clasificados]
                if (corte["pts"], corte["dg"], corte["gf"]) == (siguiente["pts"], siguiente["dg"], siguiente["gf"]):
                    raise DomainRuleError(
                        "Hay un empate en el corte de clasificación a la liguilla (puntos, diferencia de gol y "
                        "goles a favor iguales) — resolvé el orden manual en la tabla de posiciones antes de "
                        "generar los playoffs."
                    )
            equipo_ids_tabla = [fila["equipo_id"] for fila in tabla[:n_clasificados]]
            cruce, seeds = self._cruzar_tabla_unica(equipo_ids_tabla)

        nueva_fase = Fase(
            torneo_id=torneo_id,
            nombre="Eliminatoria",
            tipo="Eliminacion",
            orden=fase_regular.orden + 1,
            estado="Pendiente",
        )
        self.session.add(nueva_fase)
        await self.session.flush()

        await self._sortear_bracket(
            torneo, nueva_fase, usuario_id, semilla=None, equipo_ids=cruce, barajar=False,
            formato_eliminatoria=torneo.formato_eliminatoria, seeds=seeds,
        )
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

    # ---------- Cierre de Fase Regular (podio) ----------

    async def _ganador_partido_o_llave(self, partido: Partido) -> int:
        """Reusa `fn_marcador_partido`/`fn_resolver_llave` (06_triggers.sql)
        vía una consulta directa en vez de reimplementar la misma regla en
        Python — una sola fuente de verdad para "quién ganó". `partido`
        tiene que ser el nodo CANÓNICO (la vuelta si es una llave a dos
        partidos)."""
        if partido.partido_ida_id is not None:
            result = await self.session.execute(
                text("SELECT ganador_equipo_id FROM fn_resolver_llave(:id)"), {"id": partido.id}
            )
        else:
            result = await self.session.execute(
                text("SELECT ganador_equipo_id FROM fn_marcador_partido(:id)"), {"id": partido.id}
            )
        ganador = result.scalar_one_or_none()
        if ganador is None:
            raise DomainRuleError(
                "No se pudo determinar un ganador — revisá que el desempate del partido esté cargado."
            )
        return ganador

    async def _podio_desde_bracket(self, fase: Fase) -> tuple[int, int, int | None]:
        """C3, camino Eliminación (torneo `Eliminacion` puro, o playoffs de
        `Grupos_Playoffs`/`Liga` ya jugados): campeón/subcampeón salen de
        la Final resuelta; tercero, del partido de Tercer Lugar si existe
        y ya terminó, NULL si no (un bracket de 2 equipos no tiene
        Tercer Lugar — EC-58)."""
        partidos = await self._partidos_de_fase(fase.id)
        referenciados_como_ida = {p.partido_ida_id for p in partidos if p.partido_ida_id is not None}
        final = next(
            (p for p in partidos if p.ronda_nombre == "Final" and p.id not in referenciados_como_ida),
            None,
        )
        if final is None:
            raise DomainRuleError("No se encontró la Final de este bracket.")
        if final.estado != "Finalizado":
            raise DomainRuleError("La Final todavía no está resuelta.")

        campeon = await self._ganador_partido_o_llave(final)
        subcampeon = final.equipos_id_visitante if campeon == final.equipos_id_local else final.equipos_id_local

        tercero = None
        tercer_lugar = next((p for p in partidos if p.ronda_nombre == "Tercer Lugar"), None)
        if tercer_lugar is not None and tercer_lugar.estado == "Finalizado":
            tercero = await self._ganador_partido_o_llave(tercer_lugar)
        return campeon, subcampeon, tercero

    async def _podio_desde_tabla(
        self, torneo_id: int, orden_podio: list[int] | None
    ) -> tuple[int | None, int | None, int | None]:
        """C3, camino Liga: podio = primeros 3 de la tabla de posiciones.

        Finding 2 / Taste Decision T1: `vw_tabla_posiciones` no tiene
        desempate de última instancia en Liga (`Orden_Manual` cuelga de
        `GRUPO_EQUIPO`, siempre NULL sin grupos) — un empate real en pts/
        dg/gf se resuelve con `orden_podio` explícito del admin, nunca
        alfabéticamente. El servidor valida que cada equipo mandado esté
        REALMENTE empatado con el que desplaza."""
        tabla = await self.estadisticas_repo.tabla_posiciones(torneo_id)
        slots = min(3, len(tabla))
        if slots < 1:
            raise DomainRuleError("No hay equipos con partidos jugados — no se puede armar el podio.")
        # Finding 9: un torneo con menos filas jugadas que "primeros 3"
        # (partidos cancelados, o un equipo que nunca jugó) no corona a
        # nadie con PJ=0.
        if any(fila["pj"] == 0 for fila in tabla[:slots]):
            raise DomainRuleError("Hay un equipo en el podio que todavía no jugó ningún partido.")

        # Agrupa la tabla en bloques de empate real (mismo pts/dg/gf),
        # preservando el orden que ya trae el repositorio para todo lo
        # demás.
        bloques: list[list[dict]] = []
        for fila in tabla:
            clave = (fila["pts"], fila["dg"], fila["gf"])
            if bloques and (bloques[-1][0]["pts"], bloques[-1][0]["dg"], bloques[-1][0]["gf"]) == clave:
                bloques[-1].append(fila)
            else:
                bloques.append([fila])

        if orden_podio is not None:
            ids_en_tabla = {fila["equipo_id"] for fila in tabla}
            for equipo_id in orden_podio:
                if equipo_id not in ids_en_tabla:
                    raise DomainRuleError(f"El equipo {equipo_id} no está inscripto (o no jugó) en este torneo.")
            ids_empatados: set[int] = set()
            for bloque in bloques:
                if len(bloque) > 1:
                    ids_empatados.update(fila["equipo_id"] for fila in bloque)
            for equipo_id in orden_podio:
                if equipo_id not in ids_empatados:
                    raise DomainRuleError(f"El equipo {equipo_id} no está empatado con nadie — no se puede reordenar.")

            posicion_pedida = {equipo_id: i for i, equipo_id in enumerate(orden_podio)}
            tabla_final: list[dict] = []
            for bloque in bloques:
                if len(bloque) == 1:
                    tabla_final.extend(bloque)
                    continue
                por_id = {fila["equipo_id"]: fila for fila in bloque}
                ordenados = sorted(bloque, key=lambda f: posicion_pedida.get(f["equipo_id"], len(orden_podio)))
                tabla_final.extend(ordenados)
        else:
            # Sin orden manual: un empate real en el corte del podio se
            # rechaza — nunca se decide alfabéticamente (Finding 2).
            posicion = 0
            for bloque in bloques:
                if len(bloque) > 1 and posicion < slots:
                    raise DomainRuleError(
                        "Hay un empate en el podio (puntos, diferencia de gol y goles a favor iguales) — "
                        "ordená los equipos empatados antes de cerrar el torneo."
                    )
                posicion += len(bloque)
            tabla_final = tabla

        campeon = tabla_final[0]["equipo_id"] if slots >= 1 else None
        subcampeon = tabla_final[1]["equipo_id"] if slots >= 2 else None
        tercero = tabla_final[2]["equipo_id"] if slots >= 3 else None
        return campeon, subcampeon, tercero

    async def cerrar_torneo(
        self, torneo_id: int, usuario_id: int, orden_podio: list[int] | None = None
    ) -> Torneo:
        """C3/C4 — resuelve el podio y lo persiste. Rechaza con 400 (no es
        idempotente — CEO review corrige "idempotente" del borrador) si el
        torneo ya está cerrado, si la fase actual no está 100% terminada
        (Finalizado o Cancelado, nunca "100% Finalizado" literal — un
        partido Cancelado nunca llega a Finalizado), o si la fase ACTUAL
        (nunca `Torneo.Formato`, Finding del review: eso dejaría
        Grupos_Playoffs permanentemente incerrable incluso tras terminar
        sus playoffs) es de tipo Grupos.

        `orden_podio`: desempate explícito del admin para un podio de Liga
        empatado en pts/dg/gf (Finding 2 / T1) — se persiste en
        `Torneo.Orden_Podio_Manual` para sobrevivir un `reabrir_torneo` +
        re-cierre sin que el admin tenga que rehacer el desempate."""
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        if torneo.estado == "Finalizado":
            raise DomainRuleError("Este torneo ya está cerrado.")

        fase_actual = await self.fase_repo.ultima_por_torneo(torneo_id)
        if fase_actual is None:
            raise DomainRuleError("Este torneo todavía no tiene ninguna fase generada.")
        if fase_actual.tipo == "Grupos":
            raise DomainRuleError(
                "No se puede cerrar directamente un torneo en Formato Grupos — generá los Playoffs primero."
            )

        partidos = await self._partidos_de_fase(fase_actual.id)
        if not partidos:
            raise DomainRuleError("Esta fase todavía no tiene partidos generados.")
        if any(p.estado not in ("Finalizado", "Cancelado") for p in partidos):
            raise DomainRuleError("La fase actual todavía tiene partidos sin terminar.")

        if fase_actual.tipo == "Liga":
            orden_efectivo = orden_podio if orden_podio is not None else torneo.orden_podio_manual
            campeon, subcampeon, tercero = await self._podio_desde_tabla(torneo_id, orden_efectivo)
        else:  # Eliminacion
            campeon, subcampeon, tercero = await self._podio_desde_bracket(fase_actual)

        torneo.campeon_equipo_id = campeon
        torneo.subcampeon_equipo_id = subcampeon
        torneo.tercer_puesto_equipo_id = tercero
        torneo.fecha_cierre = datetime.now(timezone.utc).replace(tzinfo=None)
        if orden_podio is not None:
            torneo.orden_podio_manual = orden_podio
        torneo.estado = "Finalizado"
        fase_actual.estado = "Finalizada"
        await self.session.commit()
        await self.session.refresh(torneo)
        logger.info(
            "cerrar_torneo torneo_id=%s usuario_id=%s campeon=%s subcampeon=%s tercero=%s fase_id=%s",
            torneo_id, usuario_id, campeon, subcampeon, tercero, fase_actual.id,
        )
        return torneo

    async def reabrir_torneo(self, torneo_id: int, usuario_id: int) -> Torneo:
        """Finding 4 / T3: `POST /torneos/{id}/reabrir` en la misma versión
        que `cerrar_torneo` — sin esto, un podio equivocado (o un torneo
        cerrado por error) queda permanente. Limpia los 3 FK de podio +
        Fecha_Cierre y devuelve la última FASE a En_Curso. Deja
        `Orden_Podio_Manual` INTACTO a propósito (CEO review): el
        desempate ya resuelto a mano no se pierde y se re-ofrece como
        default en el próximo cierre."""
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        if torneo.estado != "Finalizado":
            raise DomainRuleError("Este torneo no está cerrado.")

        fase_actual = await self.fase_repo.ultima_por_torneo(torneo_id)
        torneo.campeon_equipo_id = None
        torneo.subcampeon_equipo_id = None
        torneo.tercer_puesto_equipo_id = None
        torneo.fecha_cierre = None
        torneo.estado = "Activo"
        if fase_actual is not None:
            fase_actual.estado = "En_Curso"
        await self.session.commit()
        await self.session.refresh(torneo)
        logger.info(
            "reabrir_torneo torneo_id=%s usuario_id=%s fase_id=%s",
            torneo_id, usuario_id, fase_actual.id if fase_actual else None,
        )
        return torneo

    async def estado_fase(self, torneo_id: int) -> dict:
        """C4 — fuente única de "¿la fase terminó y qué se puede hacer
        ahora?": antes `MotorFormatosPanel.tsx` reimplementaba esta regla
        en el cliente escaneando `partidos`; agregar Liga la habría
        duplicado una tercera vez. `acciones_disponibles` es lo que hace
        el frontend condicional trivial: la regla de negocio vive acá, una
        sola vez."""
        torneo = await self.torneo_repo.get_or_404(torneo_id)
        fase_actual = await self.fase_repo.ultima_por_torneo(torneo_id)
        if fase_actual is None:
            return {
                "fase_actual": None,
                "partidos_total": 0,
                "partidos_finalizados": 0,
                "partidos_cancelados": 0,
                "partidos_pendientes": 0,
                "fase_completa": False,
                "acciones_disponibles": [],
                "torneo_cerrado": torneo.estado == "Finalizado",
                "podio": None,
            }

        partidos = await self._partidos_de_fase(fase_actual.id)
        total = len(partidos)
        finalizados = sum(1 for p in partidos if p.estado == "Finalizado")
        cancelados = sum(1 for p in partidos if p.estado == "Cancelado")
        pendientes = total - finalizados - cancelados
        # Finding P1: "Finalizado o Cancelado", nunca "100% Finalizado"
        # literal — un partido cancelado nunca llega a Finalizado.
        fase_completa = total > 0 and pendientes == 0

        acciones: list[str] = []
        if torneo.estado != "Finalizado" and fase_completa:
            if fase_actual.tipo == "Liga":
                acciones = ["cerrar_directo", "generar_playoffs"]
            elif fase_actual.tipo == "Grupos":
                acciones = ["generar_playoffs"]  # Opción A no existe en Formato Grupos.
            elif fase_actual.tipo == "Eliminacion":
                acciones = ["cerrar_directo"]

        podio = None
        if torneo.estado == "Finalizado":
            diverge = False
            if fase_actual.tipo == "Liga":
                try:
                    campeon, subcampeon, tercero = await self._podio_desde_tabla(
                        torneo_id, torneo.orden_podio_manual
                    )
                    diverge = (
                        campeon != torneo.campeon_equipo_id
                        or subcampeon != torneo.subcampeon_equipo_id
                        or tercero != torneo.tercer_puesto_equipo_id
                    )
                except DomainRuleError:
                    diverge = True
            podio = {
                "campeon_equipo_id": torneo.campeon_equipo_id,
                "subcampeon_equipo_id": torneo.subcampeon_equipo_id,
                "tercer_puesto_equipo_id": torneo.tercer_puesto_equipo_id,
                "fecha_cierre": torneo.fecha_cierre,
                "diverge_de_tabla_actual": diverge,
            }

        return {
            "fase_actual": {
                "id": fase_actual.id,
                "nombre": fase_actual.nombre,
                "tipo": fase_actual.tipo,
                "estado": fase_actual.estado,
            },
            "partidos_total": total,
            "partidos_finalizados": finalizados,
            "partidos_cancelados": cancelados,
            "partidos_pendientes": pendientes,
            "fase_completa": fase_completa,
            "acciones_disponibles": acciones,
            "torneo_cerrado": torneo.estado == "Finalizado",
            "podio": podio,
        }
