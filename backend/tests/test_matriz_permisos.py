"""TASK-048 (QA-06, PR-035): matriz de autorización por rol y ruta.

Cada ruta de escritura (POST, PATCH, PUT, DELETE) declara qué espera cada
actor: 401 (sin sesión), 403 (sin permiso) u "ok" (pasa la autorización; el
estado concreto no importa: 2xx, 400, 404, 409, 422). La prueba de
exhaustividad falla si aparece una ruta de escritura que no está acá, así
que una ruta nueva obliga a decidir sus permisos.

La tabla se publica en docs/permisos.md; `test_documento_al_dia` falla si se
desincroniza. Para regenerarlo:
    python -m tests.test_matriz_permisos

Datos (05_seed.sql): torneo 1 con el grupo 1, partido 3 (Halcones=3 vs
Tiburones=1), inscripciones 1-3, vínculo de plantilla 1, perfil 1. La
fixture `datos` agrega un evento y un hito en el partido 3, un grupo con un
equipo y un traspaso, todos del torneo 1.
"""
from __future__ import annotations

import pathlib
from dataclasses import dataclass

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.asignacion_torneo_admin import AsignacionTorneoAdmin
from app.models.evento_partido import EventoPartido
from app.models.fase import Fase
from app.models.grupo import Grupo
from app.models.grupo_equipo import GrupoEquipo
from app.models.hito_partido import HitoPartido
from app.models.partido import Partido
from app.models.traspaso import Traspaso
from app.models.usuario import Usuario

ACTORES = ("anonimo", "publico", "arbitro_ajeno", "arbitro", "admin_sin_torneo", "admin_del_torneo", "admin_general")
ETIQUETAS = {
    "anonimo": "Anónimo",
    "publico": "Publico",
    "arbitro_ajeno": "Árbitro (otro partido)",
    "arbitro": "Árbitro (su partido)",
    "admin_sin_torneo": "TorneoAdmin (sin el torneo)",
    "admin_del_torneo": "TorneoAdmin (con el torneo)",
    "admin_general": "AdminGeneral",
}
OK = "ok"

# Perfiles de permiso. El orden de los valores sigue ACTORES.
SOLO_ADMIN_GENERAL = ("401", "403", "403", "403", "403", "403", OK)
CUALQUIER_TORNEO_ADMIN = ("401", "403", "403", "403", OK, OK, OK)
ADMIN_DEL_TORNEO = ("401", "403", "403", "403", "403", OK, OK)
MESA_DEL_PARTIDO = ("401", "403", "403", OK, "403", OK, OK)
CON_SESION = ("401", OK, OK, OK, OK, OK, OK)

# Rutas que no llevan autorización a propósito.
EXENTAS = {("POST", "/api/v1/auth/login"): "Es el login: pública por definición."}


@dataclass(frozen=True)
class Caso:
    metodo: str
    ruta: str  # con los parámetros ya resueltos: {evento_partido}, {hito}... los llena la fixture
    perfil: tuple[str, ...]
    cuerpo: dict | None = None
    nota: str = ""


MATRIZ: list[Caso] = [
    # Cuenta propia (TASK-033): cualquier sesión. La actual incorrecta da 400.
    Caso("POST", "/api/v1/auth/cambiar-password", CON_SESION, {"password_actual": "no-es-la-actual", "password_nueva": "otra-clave-larga-1"}),
    # Catálogos de sistema (TASK-013)
    Caso("PATCH", "/api/v1/disciplinas/1", SOLO_ADMIN_GENERAL, {"estado": "Activo"}),
    Caso("PATCH", "/api/v1/modalidades/1", SOLO_ADMIN_GENERAL, {"estado": "Activo"}),
    Caso("POST", "/api/v1/eventos", SOLO_ADMIN_GENERAL, {"nombre": "Falta matriz"}),
    Caso("PATCH", "/api/v1/eventos/1", SOLO_ADMIN_GENERAL, {"descripcion": "Gol"}),
    Caso("DELETE", "/api/v1/eventos/1", SOLO_ADMIN_GENERAL),
    # Usuarios
    Caso("POST", "/api/v1/usuarios", SOLO_ADMIN_GENERAL, {"username": "nuevo_matriz", "password": "clave-larga-123", "nombre": "N", "rol": "Publico"}),
    Caso("PATCH", "/api/v1/usuarios/{publico}", SOLO_ADMIN_GENERAL, {"nombre": "Publico Matriz"}),
    Caso("DELETE", "/api/v1/usuarios/{publico}", SOLO_ADMIN_GENERAL),
    Caso("PATCH", "/api/v1/usuarios/{publico}/licencia", SOLO_ADMIN_GENERAL, {"licencia_activa": True}),
    Caso("PATCH", "/api/v1/usuarios/{admin_sin_torneo}/torneos", SOLO_ADMIN_GENERAL, {"torneo_ids": []}),
    # Catálogo compartido de equipos y jugadores (TASK-013: editar es de
    # cualquier organizador; dar de baja exige los torneos donde participa)
    Caso("POST", "/api/v1/equipos", CUALQUIER_TORNEO_ADMIN, {"nombre": "Equipo Matriz", "disciplina_id": 1, "modalidad_id": 1}),
    Caso("PATCH", "/api/v1/equipos/1", CUALQUIER_TORNEO_ADMIN, {"nombre": "Tiburones FC"}),
    Caso("DELETE", "/api/v1/equipos/1", ADMIN_DEL_TORNEO, nota="Baja: exige administrar los torneos abiertos donde juega."),
    Caso("POST", "/api/v1/equipos/1/plantilla-base", CUALQUIER_TORNEO_ADMIN, {"jugador_id": 1}),
    Caso("DELETE", "/api/v1/equipos/1/plantilla-base/999999", CUALQUIER_TORNEO_ADMIN),
    Caso("POST", "/api/v1/jugadores", CUALQUIER_TORNEO_ADMIN, {"nombre": "J Matriz", "cedula": "MATRIZ001", "correo_electronico": "m@t.com"}),
    Caso("PATCH", "/api/v1/jugadores/1", CUALQUIER_TORNEO_ADMIN, {"nombre": "Carlos Pérez"}),
    Caso("DELETE", "/api/v1/jugadores/1", ADMIN_DEL_TORNEO, nota="Baja: exige administrar los torneos abiertos donde juega."),
    Caso("POST", "/api/v1/perfiles", CUALQUIER_TORNEO_ADMIN, {"jugador_id": 1, "disciplina_id": 1}),
    Caso("PATCH", "/api/v1/perfiles/1", ADMIN_DEL_TORNEO, {"suspendido": False}, nota="Suspensión: exige administrar los torneos abiertos donde juega."),
    # Torneos
    Caso("POST", "/api/v1/torneos", CUALQUIER_TORNEO_ADMIN, {"torneo_grupo_nombre": "Torneo Matriz", "disciplina_id": 1, "modalidad_id": 1, "fecha_inicio": "2026-05-01", "fecha_fin": "2026-06-01"}),
    Caso("PATCH", "/api/v1/torneo-grupos/1", ADMIN_DEL_TORNEO, {"nombre": "Copa Ecotec"}),
    Caso("PATCH", "/api/v1/torneos/1", ADMIN_DEL_TORNEO, {"nombre": "Copa Ecotec 2026"}),
    Caso("DELETE", "/api/v1/torneos/1", ADMIN_DEL_TORNEO),
    Caso("POST", "/api/v1/torneos/1/cerrar", ADMIN_DEL_TORNEO, {}),
    Caso("POST", "/api/v1/torneos/1/reabrir", ADMIN_DEL_TORNEO),
    Caso("POST", "/api/v1/torneos/1/fixture", ADMIN_DEL_TORNEO),
    Caso("POST", "/api/v1/torneos/1/sorteo", ADMIN_DEL_TORNEO, {}),
    Caso("POST", "/api/v1/torneos/1/playoffs", ADMIN_DEL_TORNEO, {}),
    Caso("PATCH", "/api/v1/grupos/equipos/{grupo_equipo}", ADMIN_DEL_TORNEO, {"orden_manual": 1}),
    # Inscripciones, plantillas y traspasos del torneo 1
    Caso("POST", "/api/v1/inscripciones", ADMIN_DEL_TORNEO, {"torneo_id": 1, "equipo_id": 1}),
    Caso("PATCH", "/api/v1/inscripciones/1", ADMIN_DEL_TORNEO, {"estado": "Confirmado"}),
    Caso("POST", "/api/v1/plantillas", ADMIN_DEL_TORNEO, {"jugador_perfil_id": 1, "inscripcion_torneo_id": 1, "fecha_inicio": "2026-01-01"}),
    Caso("PATCH", "/api/v1/plantillas/1", ADMIN_DEL_TORNEO, {"dorsal": 10}),
    Caso("POST", "/api/v1/plantillas/1/baja?fecha_fin=2026-12-31", ADMIN_DEL_TORNEO),
    Caso("POST", "/api/v1/plantillas/lote/validar", ADMIN_DEL_TORNEO, {"inscripcion_torneo_id": 1, "fecha_inicio": "2026-01-01", "filas": []}),
    Caso("POST", "/api/v1/plantillas/lote/confirmar", ADMIN_DEL_TORNEO, {"inscripcion_torneo_id": 1, "fecha_inicio": "2026-01-01", "filas": []}),
    Caso("POST", "/api/v1/traspasos", ADMIN_DEL_TORNEO, {"jugador_perfil_id": 1, "inscripcion_origen_id": 1, "inscripcion_destino_id": 2}),
    Caso("POST", "/api/v1/traspasos/{traspaso}/anular", ADMIN_DEL_TORNEO),
    # Partidos: organización
    Caso("POST", "/api/v1/partidos", ADMIN_DEL_TORNEO, {"torneo_id": 1, "equipos_id_local": 1, "equipos_id_visitante": 2, "fecha_partido": "2026-03-01T16:00:00"}),
    Caso("DELETE", "/api/v1/partidos/3", ADMIN_DEL_TORNEO),
    Caso("POST", "/api/v1/partidos/3/reclamo", ADMIN_DEL_TORNEO, {"equipo_id": 1, "motivo": "matriz"}),
    # Partidos: mesa (el árbitro, solo en SU partido — TASK-021 acota además
    # qué campos puede tocar en el PATCH)
    Caso("PATCH", "/api/v1/partidos/3", MESA_DEL_PARTIDO, {"hubo_tiempo_extra": False}),
    Caso("PUT", "/api/v1/partidos/3/convocados", MESA_DEL_PARTIDO, {"convocados": []}),
    Caso("POST", "/api/v1/partidos/3/convocados", MESA_DEL_PARTIDO, {"jugador_perfil_id": 5}),
    Caso("POST", "/api/v1/partidos/3/hitos", MESA_DEL_PARTIDO, {"tipo_hito": "Pausa"}),
    Caso("PATCH", "/api/v1/partidos/3/hitos/{hito}", MESA_DEL_PARTIDO, {"minuto_reloj": 1}),
    Caso("POST", "/api/v1/partidos/3/deshacer-cierre-forzado", MESA_DEL_PARTIDO),
    Caso("POST", "/api/v1/partidos/3/walkover", MESA_DEL_PARTIDO, {"equipo_ausente_id": 3}),
    Caso("POST", "/api/v1/partidos/3/resultado-directo", MESA_DEL_PARTIDO, {"eventos": []}),
    Caso("POST", "/api/v1/eventos-partido", MESA_DEL_PARTIDO, {"partidos_id": 3, "jugador_id": 5, "equipo_id": 3, "eventos_id": 1}),
    Caso("PATCH", "/api/v1/eventos-partido/{evento_partido}", MESA_DEL_PARTIDO, {"minuto": 5}),
    Caso("POST", "/api/v1/eventos-partido/{evento_partido}/anular", MESA_DEL_PARTIDO),
]


def _plantilla_de_ruta(ruta: str) -> str:
    """De la ruta concreta a la plantilla de FastAPI, para comparar con
    app.routes: /api/v1/torneos/1 -> /api/v1/torneos/{}."""
    sin_query = ruta.split("?")[0]
    partes = []
    for parte in sin_query.split("/"):
        partes.append("{}" if (parte.isdigit() or (parte.startswith("{") and parte.endswith("}"))) else parte)
    return "/".join(partes)


def _rutas_de_escritura() -> set[tuple[str, str]]:
    def recorrer(rutas, prefijo=""):
        for r in rutas:
            if type(r).__name__ == "_IncludedRouter":
                yield from recorrer(r.original_router.routes, prefijo + (r.include_context.prefix or ""))
            elif getattr(r, "methods", None):
                yield prefijo + r.path, r.methods

    resultado = set()
    for ruta, metodos in recorrer(app.routes):
        for metodo in metodos & {"POST", "PATCH", "PUT", "DELETE"}:
            resultado.add((metodo, _plantilla_de_ruta(ruta)))
    return resultado


# ---------- Datos y actores ----------


@pytest.fixture
async def datos(db_session: AsyncSession) -> dict[str, int]:
    hash_unico = hash_password("matriz-clave-1234")
    usuarios = {}
    for actor, rol in (
        ("publico", "Publico"),
        ("arbitro_ajeno", "Arbitro"),
        ("arbitro", "Arbitro"),
        ("admin_sin_torneo", "TorneoAdmin"),
        ("admin_del_torneo", "TorneoAdmin"),
        ("admin_general", "AdminGeneral"),
    ):
        u = Usuario(username=f"matriz_{actor}", nombre=actor, password_hash=hash_unico, rol=rol)
        db_session.add(u)
        await db_session.flush()
        usuarios[actor] = u
    partido = await db_session.get(Partido, 3)
    partido.arbitro_id = usuarios["arbitro"].id
    db_session.add(AsignacionTorneoAdmin(usuario_id=usuarios["admin_del_torneo"].id, torneo_id=1, estado="Activo"))

    evento = EventoPartido(partidos_id=3, jugador_id=5, equipo_id=3, eventos_id=1, minuto=10)
    hito = HitoPartido(partido_id=3, tipo_hito="Pausa", minuto_reloj=5, registrado_por=usuarios["arbitro"].id)
    fase_id = (await db_session.execute(select(Fase.id).where(Fase.torneo_id == 1))).scalars().first()
    grupo = Grupo(fase_id=fase_id, nombre="M")
    db_session.add_all([evento, hito, grupo])
    await db_session.flush()
    grupo_equipo = GrupoEquipo(grupo_id=grupo.id, inscripcion_torneo_id=1)
    traspaso = Traspaso(
        jugador_perfil_id=1, inscripcion_origen_id=1, inscripcion_destino_id=2, realizado_por=usuarios["admin_general"].id
    )
    db_session.add_all([grupo_equipo, traspaso])
    await db_session.commit()

    return {
        "evento_partido": evento.id,
        "hito": hito.id,
        "grupo_equipo": grupo_equipo.id,
        "traspaso": traspaso.id,
        **{actor: u.id for actor, u in usuarios.items()},
        "_tokens": {actor: create_access_token(u.username, u.rol) for actor, u in usuarios.items()},
    }


def _resolver(ruta: str, datos: dict) -> str:
    for clave, valor in datos.items():
        if not clave.startswith("_"):
            ruta = ruta.replace("{" + clave + "}", str(valor))
    return ruta


def _clasificar(status: int) -> str:
    return str(status) if status in (401, 403) else OK


@pytest.mark.parametrize("caso", MATRIZ, ids=lambda c: f"{c.metodo} {c.ruta}")
async def test_matriz(client: AsyncClient, datos: dict, caso: Caso):
    """PR-035. Los actores van del menos al más privilegiado: lo que hace uno
    con permiso no le cambia el permiso a los siguientes."""
    ruta = _resolver(caso.ruta, datos)
    obtenido = {}
    for actor in ACTORES:
        headers = {} if actor == "anonimo" else {"Authorization": f"Bearer {datos['_tokens'][actor]}"}
        resp = await client.request(caso.metodo, ruta, json=caso.cuerpo, headers=headers)
        obtenido[actor] = _clasificar(resp.status_code)
    esperado = dict(zip(ACTORES, caso.perfil))
    assert obtenido == esperado


def test_todas_las_rutas_de_escritura_estan_en_la_matriz():
    """Una ruta de escritura nueva sin declarar hace fallar la suite."""
    declaradas = {(c.metodo, _plantilla_de_ruta(c.ruta)) for c in MATRIZ} | {
        (m, _plantilla_de_ruta(r)) for m, r in EXENTAS
    }
    faltan = _rutas_de_escritura() - declaradas
    sobran = declaradas - _rutas_de_escritura()
    assert not faltan, f"Rutas de escritura sin declarar en la matriz: {sorted(faltan)}"
    assert not sobran, f"Rutas declaradas que ya no existen: {sorted(sobran)}"


# ---------- Documento ----------

DOCUMENTO = pathlib.Path(__file__).resolve().parents[2] / "docs" / "permisos.md"
SIMBOLO = {OK: "✅", "401": "🔒 401", "403": "⛔ 403"}


def render_markdown() -> str:
    lineas = [
        "# Permisos por rol y ruta",
        "",
        "Generado desde `backend/tests/test_matriz_permisos.py` (TASK-048). No editar a mano:",
        "cambiá la matriz y regenerá con `python -m tests.test_matriz_permisos` desde `backend/`.",
        "La suite falla si este archivo no coincide con la matriz, o si hay una ruta de escritura",
        "sin declarar.",
        "",
        "✅ pasa la autorización (después pueden aplicar reglas de negocio) · 🔒 401 sin sesión ·",
        "⛔ 403 sin permiso. \"El torneo\" es el torneo del recurso; \"su partido\" es el partido",
        "que el árbitro tiene asignado.",
        "",
        "| Método | Ruta | " + " | ".join(ETIQUETAS[a] for a in ACTORES) + " | Nota |",
        "|---|---|" + "---|" * len(ACTORES) + "---|",
    ]
    for c in MATRIZ:
        ruta = _plantilla_de_ruta(c.ruta).replace("{}", "{id}")
        celdas = " | ".join(SIMBOLO[v] for v in c.perfil)
        lineas.append(f"| {c.metodo} | `{ruta}` | {celdas} | {c.nota} |")
    lineas += ["", "## Rutas sin autorización", ""]
    for (metodo, ruta), motivo in EXENTAS.items():
        lineas.append(f"- `{metodo} {ruta}`: {motivo}")
    return "\n".join(lineas) + "\n"


def test_documento_al_dia():
    assert DOCUMENTO.exists(), "Falta docs/permisos.md: generalo con `python -m tests.test_matriz_permisos`."
    assert DOCUMENTO.read_text(encoding="utf-8").replace("\r\n", "\n") == render_markdown()


if __name__ == "__main__":
    DOCUMENTO.write_text(render_markdown(), encoding="utf-8")
    print(f"Escrito {DOCUMENTO}")
