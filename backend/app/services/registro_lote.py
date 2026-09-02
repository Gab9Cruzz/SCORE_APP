"""Registro por lote con pantalla dividida (equipos-jugadores-plan.md,
Fase 2, Etapa B). `_validar_lote` es el único lugar donde vive el
algoritmo de los edge cases EC-1/2/3/4/6/9/13/18 — lo usan tanto /validar
como /confirmar, así /confirmar revalida de verdad contra la base actual
(EC-7: no confía en el snapshot que vio el cliente)."""
from datetime import date

from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.modalidad import Modalidad
from app.repositories.equipo import EquipoRepository
from app.repositories.inscripcion_torneo import InscripcionTorneoRepository
from app.repositories.jugador import JugadorRepository
from app.repositories.jugador_equipo import JugadorEquipoRepository
from app.repositories.jugador_perfil_disciplina import JugadorPerfilDisciplinaRepository
from app.repositories.modalidad import ModalidadRepository
from app.repositories.torneo import TorneoRepository
from app.schemas.registro_lote import FilaInvalida, FilaValida, RegistroLoteFila


def _tope_de_plantilla(modalidad: Modalidad) -> int | None:
    """3B-4 (docs/plans/cierre-backlog-todos-plan.md): el tope real de esta
    modalidad para el registro por lote — `Tamano_Plantilla_Max` si el
    catálogo lo trae seteado (equipo grande con un roster máximo
    explícito, ej. Fútbol 11=25), si no el mismo criterio de siempre para
    Pareja (`tamano_equipo<=2`, EC-6). Para un equipo grande SIN
    `Tamano_Plantilla_Max` seteado, sigue sin haber tope — mismo
    comportamiento que antes de 3B-4."""
    if modalidad.tamano_plantilla_max is not None:
        return modalidad.tamano_plantilla_max
    if modalidad.tamano_equipo <= 2:
        return modalidad.tamano_equipo
    return None


class RegistroLoteService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.jugador_repo = JugadorRepository(session)
        self.perfil_repo = JugadorPerfilDisciplinaRepository(session)
        self.jugador_equipo_repo = JugadorEquipoRepository(session)
        self.inscripcion_repo = InscripcionTorneoRepository(session)
        self.torneo_repo = TorneoRepository(session)
        self.modalidad_repo = ModalidadRepository(session)
        self.equipo_repo = EquipoRepository(session)

    async def _validar_lote(
        self, inscripcion_torneo_id: int, filas: list[RegistroLoteFila]
    ) -> tuple[list[FilaValida], list[FilaInvalida]]:
        inscripcion = await self.inscripcion_repo.get_or_404(inscripcion_torneo_id)
        torneo = await self.torneo_repo.get_or_404(inscripcion.torneo_id)
        disciplina_id = torneo.disciplina_id

        # tamano_equipo <= 2 (Pareja): tope exacto, sin banca — dos filas y
        # se acabó (ediciones-catalogo-disciplinas-plan.md, Fase 2 parte B:
        # "sin botón + agregar fila, la modalidad fija el tamaño"). > 2
        # (Conjunto, ej. Fútbol 11): tamano_equipo es cuántos juegan A LA
        # VEZ, no el tamaño máximo de la plantilla — un plantel real lleva
        # suplentes. Desde que Modalidad_ID pasó a obligatorio para TODO
        # torneo (catálogo unificado, Decisión A1), este método ve una
        # Modalidad real incluso para disciplinas de equipo que antes
        # nunca la tenían (Tipo='Equipo' => modalidad_id NULL => sin tope
        # acá) — sin este corte, registrar un plantel de fútbol de más de
        # 11 jugadores empezaría a rechazarse, una regresión real que el
        # catálogo unificado no pedía introducir. Individual
        # (tamano_equipo=1) ya ni siquiera llega a este método: desde la
        # Decisión B1 se inscribe directo por POST /inscripciones, sin
        # pasar por Registro por Lote / una fila en EQUIPOS.
        cupo_restante: int | None = None
        tope_plantilla: int | None = None
        if torneo.modalidad_id is not None:
            modalidad = await self.modalidad_repo.get_or_404(torneo.modalidad_id)
            tope_plantilla = _tope_de_plantilla(modalidad)
            if tope_plantilla is not None:
                # EC-6 / 3B-4: serializa la LECTURA del conteo contra
                # cualquier otro /validar o /confirmar concurrente sobre la
                # MISMA inscripción — sin este lock, dos requests pueden
                # contar el mismo N de activos y ambos "ver" el último
                # cupo libre (ver InscripcionTorneoRepository.lock_cupo_inscripcion).
                # No se toma cuando no hay tope que proteger (equipo grande
                # sin Tamano_Plantilla_Max seteado, EC-A) — ni falta tomar
                # un advisory lock en el camino más frecuente del sistema.
                await self.inscripcion_repo.lock_cupo_inscripcion(inscripcion_torneo_id)
                ya_activos = await self.jugador_equipo_repo.contar_activos_en_inscripcion(inscripcion_torneo_id)
                cupo_restante = tope_plantilla - ya_activos

        # Normaliza espacios antes de cualquier comparación: la identidad es
        # la cédula (EC-3/EC-4), y unique_jugador_cedula compara el string
        # exacto — " 0900000001" y "0900000001" son cédulas "distintas" para
        # el UNIQUE aunque sean la misma persona. El frontend ya recorta
        # (RegistroLoteAdmin.tsx), pero este endpoint es la frontera de
        # confianza real: cualquier otro caller directo debe quedar cubierto
        # también (equipos-jugadores-plan.md, Fase 3 security review).
        for fila in filas:
            fila.cedula = fila.cedula.strip()

        # EC-1: cédulas duplicadas dentro del mismo lote — se detecta antes
        # de tocar la base.
        indices_por_cedula: dict[str, list[int]] = {}
        for idx, fila in enumerate(filas):
            indices_por_cedula.setdefault(fila.cedula, []).append(idx)

        validos: list[FilaValida] = []
        invalidos: list[FilaInvalida] = []
        dorsales_en_este_lote: set[int] = set()

        for idx, fila in enumerate(filas):
            indices_cedula = indices_por_cedula[fila.cedula]
            if len(indices_cedula) > 1:
                otras = ", ".join(f"fila {i + 1}" for i in indices_cedula if i != idx)
                invalidos.append(
                    FilaInvalida(
                        fila_index=idx,
                        cedula=fila.cedula,
                        nombre=fila.nombre,
                        motivo=f"Cédula duplicada en este mismo lote ({otras})",
                    )
                )
                continue

            jugador = await self.jugador_repo.get_by_cedula(fila.cedula)

            # EC-2: cédula ya registrada con otro nombre — no se sobreescribe
            # silenciosamente, el admin decide.
            if jugador is not None and jugador.nombre.strip().lower() != fila.nombre.strip().lower():
                invalidos.append(
                    FilaInvalida(
                        fila_index=idx,
                        cedula=fila.cedula,
                        nombre=fila.nombre,
                        motivo=f"El nombre no coincide con el registrado para esta cédula (registrado: {jugador.nombre})",
                    )
                )
                continue

            # EC-3/EC-4: jugador existente (reusa) o nuevo (se crea recién en
            # /confirmar) — ambos casos son válidos hasta acá.
            if jugador is not None:
                perfil = await self.perfil_repo.get_by_jugador_y_disciplina(jugador.id, disciplina_id)
                if perfil is not None:
                    # EC-9: independiente de tener o no membresía activa.
                    if perfil.suspendido:
                        invalidos.append(
                            FilaInvalida(
                                fila_index=idx,
                                cedula=fila.cedula,
                                nombre=fila.nombre,
                                motivo="Jugador suspendido en esta disciplina",
                            )
                        )
                        continue

                    # EC-18: exclusividad por torneo, anticipada acá (el
                    # trigger fn_validar_exclusividad_torneo la garantiza en
                    # el insert real, pero acá se da el motivo específico).
                    conflicto = await self.jugador_equipo_repo.get_activo_en_torneo(perfil.id, torneo.id)
                    if conflicto is not None:
                        insc_conflicto = await self.inscripcion_repo.get_or_404(conflicto.inscripcion_torneo_id)
                        equipo_conflicto = await self.equipo_repo.get_or_404(insc_conflicto.equipo_id)
                        invalidos.append(
                            FilaInvalida(
                                fila_index=idx,
                                cedula=fila.cedula,
                                nombre=fila.nombre,
                                motivo=f"Ya juega en {equipo_conflicto.nombre} este torneo — usa Traspasos en Plantillas para moverlo",
                            )
                        )
                        continue

            # EC-13: dorsal repetido — dentro del lote, o ya en uso en el
            # roster vigente. Motivo separado del de cédula (es un error de
            # formulario, no de identidad).
            if fila.dorsal is not None:
                if fila.dorsal in dorsales_en_este_lote:
                    invalidos.append(
                        FilaInvalida(
                            fila_index=idx,
                            cedula=fila.cedula,
                            nombre=fila.nombre,
                            motivo=f"Dorsal {fila.dorsal} repetido en este mismo lote",
                        )
                    )
                    continue
                if await self.jugador_equipo_repo.dorsal_en_uso(inscripcion_torneo_id, fila.dorsal):
                    invalidos.append(
                        FilaInvalida(
                            fila_index=idx,
                            cedula=fila.cedula,
                            nombre=fila.nombre,
                            motivo=f"El dorsal {fila.dorsal} ya está en uso en este equipo",
                        )
                    )
                    continue

            # EC-6 / 3B-4: cupo de la modalidad (Pareja por tamano_equipo, o
            # equipo grande con Tamano_Plantilla_Max seteado — ver
            # _tope_de_plantilla más arriba).
            if cupo_restante is not None and cupo_restante <= 0:
                invalidos.append(
                    FilaInvalida(
                        fila_index=idx,
                        cedula=fila.cedula,
                        nombre=fila.nombre,
                        motivo=f"Esta modalidad admite máximo {tope_plantilla} jugadores por equipo",
                    )
                )
                continue

            if cupo_restante is not None:
                cupo_restante -= 1
            if fila.dorsal is not None:
                dorsales_en_este_lote.add(fila.dorsal)

            validos.append(
                FilaValida(
                    fila_index=idx,
                    cedula=fila.cedula,
                    nombre=fila.nombre,
                    correo_electronico=fila.correo_electronico,
                    dorsal=fila.dorsal,
                    jugador_id=jugador.id if jugador is not None else None,
                )
            )

        return validos, invalidos

    async def validar(
        self, inscripcion_torneo_id: int, filas: list[RegistroLoteFila]
    ) -> tuple[list[FilaValida], list[FilaInvalida]]:
        return await self._validar_lote(inscripcion_torneo_id, filas)

    async def confirmar(
        self, inscripcion_torneo_id: int, fecha_inicio: date, filas: list[RegistroLoteFila]
    ) -> tuple[list[JugadorEquipo], list[FilaInvalida]]:
        # EC-7: revalida de nuevo contra la base actual, no confía en lo que
        # el cliente vio en /validar — otro admin pudo haber tocado esos
        # datos justo en el medio.
        validos, invalidos = await self._validar_lote(inscripcion_torneo_id, filas)

        inscripcion = await self.inscripcion_repo.get_or_404(inscripcion_torneo_id)
        torneo = await self.torneo_repo.get_or_404(inscripcion.torneo_id)

        # EC-6: el `cupo_restante` que ya calculó _validar_lote arriba (bajo
        # el lock de esta misma llamada) deja de valer acá — cada
        # `self.session.commit()` del loop de abajo cierra la transacción y
        # con ella libera pg_advisory_xact_lock, así que el lock tomado en
        # _validar_lote ya no protege nada para la segunda fila en adelante.
        # Se vuelve a tomar y a re-leer el conteo real fila por fila, dentro
        # de la MISMA transacción que hace el INSERT (mismo criterio que
        # lock_exclusividad_torneo un poco más abajo).
        tope_confirmar: int | None = None
        if torneo.modalidad_id is not None:
            modalidad_candidata = await self.modalidad_repo.get_or_404(torneo.modalidad_id)
            tope_confirmar = _tope_de_plantilla(modalidad_candidata)

        insertados: list[JugadorEquipo] = []
        rechazados: list[FilaInvalida] = list(invalidos)

        for fila in validos:
            try:
                # Las tres escrituras de esta fila (jugador nuevo, perfil
                # nuevo, vínculo de roster) van en un solo commit al final,
                # no una por `BaseRepository.create()` como antes: si el
                # INSERT del vínculo fallara (carrera de milisegundos con
                # otro admin, dorsal recién tomado) después de que el
                # jugador/perfil ya hubieran hecho commit por separado,
                # quedaba un Jugador y un Perfil huérfanos y comprometidos
                # en la base aunque la fila se reportara como rechazada —
                # mismo criterio de atomicidad que TraspasoService.crear.
                if fila.jugador_id is not None:
                    jugador = await self.jugador_repo.get_or_404(fila.jugador_id)
                else:
                    jugador = Jugador(
                        nombre=fila.nombre, cedula=fila.cedula, correo_electronico=fila.correo_electronico
                    )
                    self.session.add(jugador)
                    await self.session.flush()  # asigna jugador.id sin comprometer la transacción

                perfil = await self.perfil_repo.get_by_jugador_y_disciplina(jugador.id, torneo.disciplina_id)
                if perfil is None:
                    perfil = JugadorPerfilDisciplina(jugador_id=jugador.id, disciplina_id=torneo.disciplina_id)
                    self.session.add(perfil)
                    await self.session.flush()

                # Serializa contra otra transacción concurrente activando el
                # mismo perfil en el mismo torneo — fn_validar_exclusividad_torneo
                # por sí sola no alcanza (ver docstring del método).
                await self.jugador_equipo_repo.lock_exclusividad_torneo(perfil.id, torneo.id)

                if tope_confirmar is not None:
                    # EC-6 / 3B-4, re-chequeo dentro del lock (ver comentario
                    # arriba de este loop) — otro /confirmar pudo haber
                    # tomado el último cupo entre que _validar_lote contó y
                    # acá.
                    await self.inscripcion_repo.lock_cupo_inscripcion(inscripcion_torneo_id)
                    ya_activos = await self.jugador_equipo_repo.contar_activos_en_inscripcion(
                        inscripcion_torneo_id
                    )
                    if ya_activos >= tope_confirmar:
                        await self.session.rollback()
                        rechazados.append(
                            FilaInvalida(
                                fila_index=fila.fila_index,
                                cedula=fila.cedula,
                                nombre=fila.nombre,
                                motivo=(
                                    f"Esta modalidad admite máximo {tope_confirmar} "
                                    "jugadores por equipo — otro registro tomó el cupo justo antes."
                                ),
                            )
                        )
                        continue

                vinculo = JugadorEquipo(
                    jugador_perfil_id=perfil.id,
                    inscripcion_torneo_id=inscripcion_torneo_id,
                    dorsal=fila.dorsal,
                    fecha_inicio=fecha_inicio,
                )
                self.session.add(vinculo)
                await self.session.commit()
                await self.session.refresh(vinculo)
                insertados.append(vinculo)
            except (IntegrityError, DBAPIError):
                # Carrera de milisegundos entre la revalidación y el insert
                # real (rarísimo, pero db/session.py ya documenta por qué
                # hace falta el rollback explícito acá: si no, la sesión
                # queda envenenada para el resto de las filas del lote).
                # Con las tres escrituras en un solo commit (arriba), este
                # rollback deshace también el jugador/perfil de ESTA fila si
                # llegaron a flushearse — no quedan huérfanos.
                await self.session.rollback()
                rechazados.append(
                    FilaInvalida(
                        fila_index=fila.fila_index,
                        cedula=fila.cedula,
                        nombre=fila.nombre,
                        motivo="Otro admin registró este dato justo antes — revisar e intentar de nuevo.",
                    )
                )

        return insertados, rechazados
