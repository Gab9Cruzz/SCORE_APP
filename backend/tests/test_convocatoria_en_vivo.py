"""Edición de la convocatoria según el estado del partido
(docs/plans/gestionar-partido-alineaciones-plan.md, D3 revisada).

Dos superficies con semántica distinta:
- `PUT` reescribe la alineación completa. Solo ANTES del arranque.
- `POST` suma un convocado. Aditivo, así que también funciona en curso — es el
  camino de las llegadas tardías.

El gate se ancla al hito `Inicio_Partido`, NO a `PARTIDOS.Estado`: `PATCH
/partidos/{id}` acepta `estado` sin validar transiciones, así que un gate por
estado se saltearía en un request.
"""
from datetime import date, datetime

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.convocado_a_partido import ConvocadoAPartido
from app.models.disciplina import Disciplina
from app.models.equipo import Equipo
from app.models.evento import Evento
from app.models.evento_partido import EventoPartido
from app.models.hito_partido import HitoPartido
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.jugador import Jugador
from app.models.jugador_equipo import JugadorEquipo
from app.models.jugador_perfil_disciplina import JugadorPerfilDisciplina
from app.models.modalidad import Modalidad
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.models.usuario import Usuario


async def _armar(db_session: AsyncSession, nombre: str, jugadores_por_equipo: int = 3) -> dict:
    disciplina = Disciplina(nombre=f"Disc {nombre}")
    db_session.add(disciplina)
    await db_session.flush()
    modalidad = Modalidad(disciplina_id=disciplina.id, nombre=f"Mod {nombre}", tamano_equipo=2)
    db_session.add(modalidad)
    await db_session.flush()

    grupo = TorneoGrupo(nombre=f"Grupo {nombre}")
    db_session.add(grupo)
    await db_session.flush()
    torneo = Torneo(
        nombre=f"Torneo {nombre}",
        disciplina_id=disciplina.id,
        modalidad_id=modalidad.id,
        torneo_grupo_id=grupo.id,
        numero_edicion=1,
        fecha_inicio=date(2026, 7, 1),
        fecha_fin=date(2026, 8, 1),
    )
    db_session.add(torneo)
    await db_session.flush()
    db_session.add(ConfiguracionTiempoTorneo(torneo_id=torneo.id, tipo_cronometro="Corrido"))

    local = Equipo(nombre=f"{nombre} L", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    visitante = Equipo(nombre=f"{nombre} V", disciplina_id=disciplina.id, modalidad_id=modalidad.id)
    db_session.add_all([local, visitante])
    await db_session.flush()
    insc_l = InscripcionTorneo(torneo_id=torneo.id, equipo_id=local.id)
    insc_v = InscripcionTorneo(torneo_id=torneo.id, equipo_id=visitante.id)
    db_session.add_all([insc_l, insc_v])
    await db_session.flush()

    partido = Partido(
        torneo_id=torneo.id,
        equipos_id_local=local.id,
        equipos_id_visitante=visitante.id,
        fecha_partido=datetime(2026, 7, 5, 10, 0, 0),
        estado="Programado",
    )
    db_session.add(partido)
    await db_session.flush()

    perfiles = {"local": [], "visitante": []}
    jugadores = {"local": [], "visitante": []}
    for lado, insc, equipo in (("local", insc_l, local), ("visitante", insc_v, visitante)):
        for i in range(jugadores_por_equipo):
            jug = Jugador(
                nombre=f"{nombre} {lado} {i}",
                cedula=f"66{abs(hash(nombre + lado)) % 10000}{i}",
                correo_electronico=f"{nombre}.{lado}.{i}@example.com".lower(),
            )
            db_session.add(jug)
            await db_session.flush()
            perfil = JugadorPerfilDisciplina(jugador_id=jug.id, disciplina_id=disciplina.id)
            db_session.add(perfil)
            await db_session.flush()
            db_session.add(
                JugadorEquipo(
                    jugador_perfil_id=perfil.id,
                    inscripcion_torneo_id=insc.id,
                    fecha_inicio=date(2026, 1, 1),
                    estado="Activo",
                )
            )
            perfiles[lado].append(perfil.id)
            jugadores[lado].append(jug.id)
    await db_session.commit()

    return {
        "partido_id": partido.id,
        "torneo_id": torneo.id,
        "equipo_local_id": local.id,
        "equipo_visitante_id": visitante.id,
        "perfiles": perfiles,
        "jugadores": jugadores,
    }


async def _arrancar(db_session: AsyncSession, partido_id: int) -> None:
    """Registra el hito de inicio directamente: el gate mira el hito, no el
    estado, así que esto es lo que hay que simular.

    `registrado_por` es NOT NULL, así que se toma cualquier usuario existente —
    quién arrancó el partido no es lo que estos tests verifican."""
    usuario_id = (await db_session.execute(select(Usuario.id).limit(1))).scalars().first()
    db_session.add(
        HitoPartido(partido_id=partido_id, tipo_hito="Inicio_Partido", registrado_por=usuario_id)
    )
    await db_session.commit()


def _cuerpo(perfiles: list[int], titulares: set[int] | None = None) -> dict:
    titulares = titulares or set()
    return {"convocados": [{"jugador_perfil_id": p, "titular": p in titulares} for p in perfiles]}


# ------------------------------------------------- PUT: solo antes del arranque


async def test_put_funciona_antes_del_arranque(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar(db_session, "PutOk")
    todos = ctx["perfiles"]["local"] + ctx["perfiles"]["visitante"]

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(todos, titulares=set(todos[:2])),
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text
    assert len(resp.json()) == len(todos)


async def test_put_rechazado_con_el_partido_ya_arrancado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar(db_session, "PutEnCurso")
    await _arrancar(db_session, ctx["partido_id"])

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(ctx["perfiles"]["local"]),
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "ya arrancó" in resp.json()["detail"]


async def test_patch_de_estado_no_reabre_la_edicion(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """El bypass que motivó anclar el gate al hito Inicio_Partido en vez de
    a PARTIDOS.Estado: `PATCH {estado:"Programado"}` -> PUT destructivo ->
    `PATCH {estado:"En curso"}`. El hito es append-only, así que ningún
    PATCH lo revierte.

    modo-vivo-sustituciones-cierre-plan.md (Bloque 0, T1/T14) cerró el
    bypass en la raíz: `estado` ya ni siquiera es un campo aceptado del
    PATCH (`PartidoUpdate.model_config = ConfigDict(extra="forbid")`) — el
    intento ahora es un 422, no un 200 que "no logra" reabrir nada. Este
    test verifica la garantía más fuerte que dejó ese fix: ya no hay
    bypass que probar, el campo se rechaza antes de llegar a ningún gate."""
    ctx = await _armar(db_session, "PutBypass")
    await _arrancar(db_session, ctx["partido_id"])

    resp = await client.patch(
        f"/api/v1/partidos/{ctx['partido_id']}",
        json={"estado": "Programado"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 422, resp.text

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo([]),
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "ya arrancó" in resp.json()["detail"]


async def test_put_rechazado_con_el_partido_cerrado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar(db_session, "PutCerrado")
    # Se setea directo en la sesión y no vía PATCH: el fixture `db_session`
    # comparte UNA transacción entre todos los requests del test y usa
    # `expire_on_commit=False`, así que el objeto que lee el service seguiría
    # cacheado con el estado viejo. En producción cada request abre su propia
    # sesión y lee el estado real.
    # 'Cancelado' y no 'Finalizado': fn_validar_ganador_corrido exige un ganador
    # para finalizar un partido de cronómetro Corrido (el que arma este helper).
    # El guard que se prueba acá trata a los dos igual.
    partido = await db_session.get(Partido, ctx["partido_id"])
    partido.estado = "Cancelado"
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(ctx["perfiles"]["local"]),
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text


# --------------------------------------------------- POST aditivo (tardíos)


async def test_post_suma_un_suplente_con_el_partido_en_curso(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """El Requerimiento 3: convocar a alguien que llegó tarde sin frenar nada."""
    ctx = await _armar(db_session, "PostVivo")
    titulares = ctx["perfiles"]["local"][:2] + ctx["perfiles"]["visitante"][:2]
    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(titulares, titulares=set(titulares)),
        headers=admin_general_headers,
    )
    await _arrancar(db_session, ctx["partido_id"])

    tardio = ctx["perfiles"]["local"][2]
    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"jugador_perfil_id": tardio, "titular": False, "minuto_ingreso": 20},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["titular"] is False
    assert resp.json()["minuto_ingreso"] == 20

    # El cronómetro no se tocó: sigue existiendo un solo hito.
    hitos = (
        await db_session.execute(
            select(HitoPartido).where(HitoPartido.partido_id == ctx["partido_id"])
        )
    ).scalars().all()
    assert len(hitos) == 1


async def test_post_en_curso_no_acepta_titular(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Con el partido en curso el flag `titular` es inmutable: el que llega
    tarde entra al banco y pasa a cancha vía el evento Cambio."""
    ctx = await _armar(db_session, "PostTitular")
    await _arrancar(db_session, ctx["partido_id"])

    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"jugador_perfil_id": ctx["perfiles"]["local"][0], "titular": True},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "suplente" in resp.json()["detail"]


async def test_post_es_idempotente_ante_doble_tap(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Un doble-tap en una cancha es normal, no un error del operador."""
    ctx = await _armar(db_session, "PostIdem")
    perfil = ctx["perfiles"]["local"][0]

    r1 = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"jugador_perfil_id": perfil},
        headers=admin_general_headers,
    )
    r2 = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"jugador_perfil_id": perfil},
        headers=admin_general_headers,
    )
    assert r1.status_code == 201, r1.text
    assert r2.status_code == 201, r2.text
    assert r1.json()["id"] == r2.json()["id"]


async def test_post_conserva_la_fecha_de_registro_de_los_ya_convocados(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Antes, cada guardado hacía DELETE masivo + INSERT y regeneraba
    `Fecha_Registro` de TODAS las filas: el dato de "a qué hora se sumó este
    jugador" —lo que justifica registrar llegadas tardías— se perdía al
    guardado siguiente."""
    ctx = await _armar(db_session, "PostFechas")
    primeros = ctx["perfiles"]["local"][:2]
    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(primeros),
        headers=admin_general_headers,
    )
    antes = {c["jugador_perfil_id"]: c["fecha_registro"] for c in (await client.get(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados"
    )).json()}

    await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"jugador_perfil_id": ctx["perfiles"]["local"][2]},
        headers=admin_general_headers,
    )
    despues = {c["jugador_perfil_id"]: c["fecha_registro"] for c in (await client.get(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados"
    )).json()}

    for perfil, fecha in antes.items():
        assert despues[perfil] == fecha


# -------------------------------------------- integridad: jugadores con eventos


async def test_no_se_puede_sacar_a_un_jugador_con_eventos(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Dejaría estadísticas colgadas de alguien que, según la alineación, no
    jugó: la vista pública mostraría el marcador con una alineación en la que no
    está el goleador."""
    ctx = await _armar(db_session, "ConEventos")
    todos = ctx["perfiles"]["local"] + ctx["perfiles"]["visitante"]
    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(todos),
        headers=admin_general_headers,
    )

    gol = (await db_session.execute(select(Evento).where(Evento.nombre == "Gol"))).scalars().first()
    db_session.add(
        EventoPartido(
            partidos_id=ctx["partido_id"],
            jugador_id=ctx["jugadores"]["local"][0],
            equipo_id=ctx["equipo_local_id"],
            eventos_id=gol.id,
            minuto=10,
            estado="Registrado",
        )
    )
    await db_session.commit()

    sin_el_goleador = [p for p in todos if p != ctx["perfiles"]["local"][0]]
    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(sin_el_goleador),
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "sucesos cargados" in resp.json()["detail"]


async def test_un_evento_anulado_no_bloquea_sacar_al_jugador(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Si el suceso se dio de baja, el jugador puede salir de la convocatoria
    sin dejar nada colgado."""
    ctx = await _armar(db_session, "EventoAnulado")
    todos = ctx["perfiles"]["local"] + ctx["perfiles"]["visitante"]
    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(todos),
        headers=admin_general_headers,
    )

    gol = (await db_session.execute(select(Evento).where(Evento.nombre == "Gol"))).scalars().first()
    db_session.add(
        EventoPartido(
            partidos_id=ctx["partido_id"],
            jugador_id=ctx["jugadores"]["local"][0],
            equipo_id=ctx["equipo_local_id"],
            eventos_id=gol.id,
            minuto=10,
            estado="Anulado",
        )
    )
    await db_session.commit()

    sin_el = [p for p in todos if p != ctx["perfiles"]["local"][0]]
    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(sin_el),
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text


# ------------------------------------------------------ concurrencia optimista


async def test_version_desactualizada_devuelve_412_con_el_estado_vigente(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """412 y no 409: el 409 ya está tomado por IntegrityError, y el cliente
    tiene que poder distinguir "alguien más editó" de "chocaste contra una
    restricción de unicidad"."""
    ctx = await _armar(db_session, "Concurrencia")
    todos = ctx["perfiles"]["local"] + ctx["perfiles"]["visitante"]
    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(todos),
        headers=admin_general_headers,
    )

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={**_cuerpo(todos[:2]), "version": "2000-01-01T00:00:00"},
        headers=admin_general_headers,
    )
    assert resp.status_code == 412, resp.text
    # El estado vigente viaja en el body: el cliente puede mostrar el diff sin
    # pedir otro GET.
    assert len(resp.json()["estado_actual"]) == len(todos)


async def test_sin_version_el_put_se_acepta(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """`version` ausente significa "no me importa": no rompe a un cliente que
    todavía no manda el campo."""
    ctx = await _armar(db_session, "SinVersion")
    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(ctx["perfiles"]["local"]),
        headers=admin_general_headers,
    )
    assert resp.status_code == 200, resp.text


async def test_cambiar_solo_el_flag_titular_se_persiste(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """El caso que rompía versionar por el set de IDs: cambiar `titular` es un
    UPDATE que no toca ningún ID, así que el set queda idéntico y dos operadores
    intercambiando titulares se pisarían en silencio. Por eso el ETag es
    `MAX(fecha_modificacion)` y no los IDs.

    NOTA: que la versión AVANCE no se puede afirmar en esta suite —
    `fecha_modificacion` la pone `CURRENT_TIMESTAMP`, que en Postgres es el
    inicio de la transacción, y el fixture `db_session` comparte una sola
    transacción entre todos los requests del test. En producción cada request
    es su propia transacción. Lo que sí se verifica acá es que el cambio de
    flag se persiste sin alterar el conjunto de convocados, que es la premisa
    del hallazgo."""
    ctx = await _armar(db_session, "VersionTitular")
    perfiles = ctx["perfiles"]["local"][:2]
    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(perfiles),
        headers=admin_general_headers,
    )
    antes = (await client.get(f"/api/v1/partidos/{ctx['partido_id']}/convocados")).json()
    assert {c["titular"] for c in antes} == {False}

    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(perfiles, titulares={perfiles[0]}),
        headers=admin_general_headers,
    )
    despues = (await client.get(f"/api/v1/partidos/{ctx['partido_id']}/convocados")).json()

    # Mismo conjunto de jugadores, distinto reparto de titulares: un versionado
    # por IDs no vería ninguna diferencia entre estos dos estados.
    assert {c["jugador_perfil_id"] for c in antes} == {c["jugador_perfil_id"] for c in despues}
    assert {c["jugador_perfil_id"] for c in despues if c["titular"]} == {perfiles[0]}


async def test_convocados_conservan_id_entre_guardados(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """Diff incremental, no DELETE+INSERT: el borrado masivo esquivaba el
    listener de auditoría, así que las bajas de convocatoria no quedaban
    registradas."""
    ctx = await _armar(db_session, "DiffIncremental")
    perfiles = ctx["perfiles"]["local"][:2]
    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(perfiles),
        headers=admin_general_headers,
    )
    ids_antes = {c["jugador_perfil_id"]: c["id"] for c in (await client.get(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados"
    )).json()}

    await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(perfiles, titulares={perfiles[0]}),
        headers=admin_general_headers,
    )
    ids_despues = {c["jugador_perfil_id"]: c["id"] for c in (await client.get(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados"
    )).json()}

    assert ids_antes == ids_despues


# ---------------------------------------------------------- alcance del roster


async def test_no_se_puede_convocar_a_alguien_de_otro_torneo(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """`plantilla_equipo` ahora filtra por torneo: sin eso se podía convocar a
    alguien del equipo en OTRO torneo — un titular fantasma que el gate no
    cuenta y al que el trigger le rechaza cualquier evento."""
    a = await _armar(db_session, "TorneoA")
    b = await _armar(db_session, "TorneoB")

    resp = await client.put(
        f"/api/v1/partidos/{a['partido_id']}/convocados",
        json=_cuerpo([b["perfiles"]["local"][0]]),
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "no pertenece" in resp.json()["detail"]


async def test_convocado_queda_registrado_con_su_autor(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    """`fecha_registro` sola no prueba nada: es el inicio de la transacción y no
    dice quién cargó al jugador."""
    ctx = await _armar(db_session, "Autoria")
    resp = await client.post(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json={"jugador_perfil_id": ctx["perfiles"]["local"][0]},
        headers=admin_general_headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["registrado_por"] is not None


async def test_convocado_a_partido_sin_rival_definido_se_rechaza(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    ctx = await _armar(db_session, "SinRival")
    partido = await db_session.get(Partido, ctx["partido_id"])
    partido.equipos_id_visitante = None
    await db_session.commit()

    resp = await client.put(
        f"/api/v1/partidos/{ctx['partido_id']}/convocados",
        json=_cuerpo(ctx["perfiles"]["local"]),
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text
    assert "dos equipos definidos" in resp.json()["detail"]
