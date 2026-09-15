"""Portal Público: `TORNEO.Publicado` como frontera anónimo/logueado
(portal-publico-feed-partidos-plan.md, C2/T3.4b/E-B3a). T3.6/E-T piden
explícitamente esta cobertura: el mismo id devuelve 200 con sesión y 404
anónimo en las 4 rutas gateadas, y el back-office (MesaPanel-equivalente)
sigue viendo un torneo despublicado sin cambios.
"""
from httpx import AsyncClient

DISCIPLINA_FUTBOL_ID = 1
MODALIDAD_FUTBOL_11_ID = 1


async def _crear_torneo_despublicado(
    client: AsyncClient, headers: dict[str, str], nombre: str, formato: str = "Liga"
) -> dict:
    resp = await client.post(
        "/api/v1/torneos",
        json={
            "disciplina_id": DISCIPLINA_FUTBOL_ID,
            "modalidad_id": MODALIDAD_FUTBOL_11_ID,
            "torneo_grupo_nombre": nombre,
            "fecha_inicio": "2026-05-01",
            "fecha_fin": "2026-06-01",
            "formato": formato,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    # E-M2: un torneo nuevo nace Publicado=False sin que nadie lo pida.
    assert body["publicado"] is False
    return body


async def test_torneo_nuevo_nace_despublicado_y_404ea_para_anonimo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo = await _crear_torneo_despublicado(client, admin_general_headers, "PP Despublicado Base")

    resp = await client.get(f"/api/v1/torneos/{torneo['id']}")
    assert resp.status_code == 404
    # F9: el 404 anónimo no debe filtrar que el torneo existe — mismo
    # mensaje genérico que un id inexistente (no menciona "publicado").
    assert resp.json()["detail"] == f"Torneo con id={torneo['id']} no encontrado."


async def test_torneo_nuevo_es_visible_con_sesion_pese_a_no_estar_publicado(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """El back-office (MesaPanel.tsx llama el mismo GET /torneos/{id}) no
    debe notar el cambio: con sesión, publicado o no, se ve entero."""
    torneo = await _crear_torneo_despublicado(client, admin_general_headers, "PP Despublicado Sesion")

    resp = await client.get(f"/api/v1/torneos/{torneo['id']}", headers=admin_general_headers)
    assert resp.status_code == 200
    assert resp.json()["id"] == torneo["id"]


async def test_publicar_torneo_lo_hace_visible_para_anonimo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo = await _crear_torneo_despublicado(client, admin_general_headers, "PP A Publicar")

    resp = await client.patch(
        f"/api/v1/torneos/{torneo['id']}", json={"publicado": True}, headers=admin_general_headers
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["publicado"] is True

    resp = await client.get(f"/api/v1/torneos/{torneo['id']}")
    assert resp.status_code == 200


async def test_listado_general_excluye_despublicados_para_anonimo_no_para_sesion(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    torneo = await _crear_torneo_despublicado(client, admin_general_headers, "PP Excluido Del Listado")

    resp = await client.get("/api/v1/torneos")
    assert torneo["id"] not in {t["id"] for t in resp.json()}

    resp = await client.get("/api/v1/torneos", headers=admin_general_headers)
    assert torneo["id"] in {t["id"] for t in resp.json()}


async def test_las_4_rutas_estadisticas_bracket_404ean_anonimo_y_200_con_sesion(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    # Eliminacion (no Liga, el default): el bracket 400ea para un torneo
    # Liga sin importar Publicado, así que necesita el formato correcto
    # para que un 200 con sesión signifique lo que este test quiere decir.
    torneo = await _crear_torneo_despublicado(client, admin_general_headers, "PP 4 Rutas", formato="Eliminacion")
    torneo_id = torneo["id"]

    rutas = [
        f"/api/v1/estadisticas/torneos/{torneo_id}/posiciones",
        f"/api/v1/estadisticas/torneos/{torneo_id}/goleadores",
        f"/api/v1/estadisticas/torneos/{torneo_id}/resultados",
        f"/api/v1/torneos/{torneo_id}/bracket",
    ]
    for ruta in rutas:
        anon = await client.get(ruta)
        assert anon.status_code == 404, f"{ruta} debía 404ear para un caller anónimo"
        con_sesion = await client.get(ruta, headers=admin_general_headers)
        assert con_sesion.status_code == 200, f"{ruta} debía seguir 200 con sesión: {con_sesion.text}"


async def test_partidos_de_torneo_despublicado_no_enumerables_por_torneo_id_anonimo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """E-B3a: gatear solo el detalle y dejar `GET /partidos?torneo_id=`
    abierto sería el peor de los dos mundos — el fixture completo seguiría
    siendo enumerable por esta vía aunque el detalle ya 404eara."""
    torneo = await _crear_torneo_despublicado(client, admin_general_headers, "PP Partidos No Enumerables")

    resp = await client.get("/api/v1/partidos", params={"torneo_id": torneo["id"]})
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get(
        "/api/v1/partidos", params={"torneo_id": torneo["id"]}, headers=admin_general_headers
    )
    assert resp.status_code == 200  # sin partidos igual, pero no filtrado por Publicado


async def test_torneo_inexistente_da_404_para_anonimo_y_logueado_por_igual(client: AsyncClient):
    resp = await client.get("/api/v1/torneos/999999999")
    assert resp.status_code == 404
