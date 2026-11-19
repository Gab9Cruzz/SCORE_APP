"""TASK-022 (ARQ-02, BE-02, FUN-18): cada caso de uso es una sola
transacción. Se inyecta un fallo en el último paso y se comprueba que no
queda nada a medias (antes, cada repositorio confirmaba por su cuenta)."""
from datetime import date, datetime

import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.exceptions.errors import DomainRuleError
from app.models.asignacion_torneo_admin import AsignacionTorneoAdmin
from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.models.equipo import Equipo
from app.models.inscripcion_torneo import InscripcionTorneo
from app.models.partido import Partido
from app.models.torneo import Torneo
from app.models.torneo_grupo import TorneoGrupo
from app.models.usuario import Usuario
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
from app.repositories.hito_partido import HitoPartidoRepository
from app.services.inscripcion_torneo import InscripcionTorneoService
from app.services.torneo import TorneoService
from tests.conftest import _crear_usuario, _login_headers


def _fallo(*_args, **_kwargs):
    raise DomainRuleError("fallo inyectado")


async def _fallo_async(*_args, **_kwargs):
    raise DomainRuleError("fallo inyectado")


async def test_fallo_al_crear_la_config_de_tiempo_no_deja_torneo_grupo_ni_fase(
    client: AsyncClient, db_session: AsyncSession, torneo_admin_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    """PR-024: el último paso de crear un torneo falla."""
    monkeypatch.setattr(TorneoService, "_crear_config_tiempo_inicial", _fallo_async)
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "torneo_grupo_nombre": "Torneo Que No Debe Quedar",
            "disciplina_id": 1,
            "modalidad_id": 1,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
        },
        headers=torneo_admin_headers,
    )
    assert resp.status_code == 400, resp.text

    db_session.expire_all()
    grupos = (await db_session.execute(select(TorneoGrupo).where(TorneoGrupo.nombre == "Torneo Que No Debe Quedar"))).all()
    torneos = (await db_session.execute(select(Torneo).where(Torneo.nombre.like("Torneo Que No Debe Quedar%")))).all()
    asignaciones = (await db_session.execute(select(func.count()).select_from(AsignacionTorneoAdmin))).scalar_one()
    assert grupos == [] and torneos == []
    assert asignaciones == 0


async def test_fallo_al_inscribir_no_deja_la_inscripcion(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    equipo = Equipo(nombre="Equipo Atomico", disciplina_id=1, modalidad_id=1)
    db_session.add(equipo)
    await db_session.commit()
    equipo_id = equipo.id

    monkeypatch.setattr(InscripcionTorneoService, "copiar_plantilla_base_al_roster", _fallo_async)
    resp = await client.post("/api/v1/inscripciones", json={"torneo_id": 1, "equipo_id": equipo_id}, headers=admin_general_headers)
    assert resp.status_code == 400, resp.text

    db_session.expire_all()
    quedaron = (await db_session.execute(select(InscripcionTorneo).where(InscripcionTorneo.equipo_id == equipo_id))).all()
    assert quedaron == []


async def test_cambio_de_rol_y_baja_de_asignaciones_van_juntos(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str], monkeypatch: pytest.MonkeyPatch
):
    usuario = await _crear_usuario(db_session, "ta_atomico", "tapass12345", "TorneoAdmin")
    db_session.add(AsignacionTorneoAdmin(usuario_id=usuario.id, torneo_id=1, estado="Activo"))
    await db_session.commit()
    usuario_id = usuario.id

    monkeypatch.setattr(AsignacionTorneoAdminRepository, "desactivar_todas_del_usuario", _fallo_async)
    resp = await client.patch(f"/api/v1/usuarios/{usuario_id}", json={"rol": "Arbitro"}, headers=admin_general_headers)
    assert resp.status_code == 400, resp.text

    db_session.expire_all()
    assert (await db_session.get(Usuario, usuario_id)).rol == "TorneoAdmin"


async def test_hito_de_fin_rechazado_no_deja_el_ganador_escrito(
    client: AsyncClient,
    db_session: AsyncSession,
    admin_general_headers: dict[str, str],
    convocar_titulares,
    monkeypatch: pytest.MonkeyPatch,
):
    """Un partido de cronómetro corrido escribe el ganador y después crea el
    hito; si el hito falla, el ganador no puede quedar."""
    grupo = TorneoGrupo(nombre="Corrido Atomico")
    db_session.add(grupo)
    await db_session.flush()
    torneo = Torneo(
        nombre="Corrido Atomico", disciplina_id=1, modalidad_id=1, torneo_grupo_id=grupo.id, numero_edicion=1,
        fecha_inicio=date(2026, 7, 1), fecha_fin=date(2026, 8, 1),
    )
    db_session.add(torneo)
    await db_session.flush()
    db_session.add(ConfiguracionTiempoTorneo(torneo_id=torneo.id, tipo_cronometro="Corrido"))
    equipo_a = Equipo(nombre="Atomico A", disciplina_id=1, modalidad_id=1)
    equipo_b = Equipo(nombre="Atomico B", disciplina_id=1, modalidad_id=1)
    db_session.add_all([equipo_a, equipo_b])
    await db_session.flush()
    db_session.add_all([
        InscripcionTorneo(torneo_id=torneo.id, equipo_id=equipo_a.id),
        InscripcionTorneo(torneo_id=torneo.id, equipo_id=equipo_b.id),
    ])
    await db_session.flush()
    partido = Partido(
        torneo_id=torneo.id, equipos_id_local=equipo_a.id, equipos_id_visitante=equipo_b.id,
        fecha_partido=datetime(2026, 7, 5, 10, 0, 0), estado="Programado",
    )
    db_session.add(partido)
    await db_session.commit()
    partido_id, equipo_a_id = partido.id, equipo_a.id

    await convocar_titulares(partido_id)
    resp = await client.post(
        f"/api/v1/partidos/{partido_id}/hitos", json={"tipo_hito": "Inicio_Partido"}, headers=admin_general_headers
    )
    assert resp.status_code == 201, resp.text

    original = HitoPartidoRepository.create

    async def _create_que_falla_en_el_fin(self, **datos):
        if datos.get("tipo_hito") == "Fin_Partido":
            raise DomainRuleError("fallo inyectado")
        return await original(self, **datos)

    monkeypatch.setattr(HitoPartidoRepository, "create", _create_que_falla_en_el_fin)
    resp = await client.post(
        f"/api/v1/partidos/{partido_id}/hitos",
        json={"tipo_hito": "Fin_Partido", "ganador_corrido_id": equipo_a_id},
        headers=admin_general_headers,
    )
    assert resp.status_code == 400, resp.text

    db_session.expire_all()
    assert (await db_session.get(Partido, partido_id)).ganador_corrido_id is None
