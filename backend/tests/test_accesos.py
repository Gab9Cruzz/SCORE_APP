"""Bitácora de inicios de sesión (ACCESOS).

El test que más importa acá es
`test_login_fallido_queda_registrado_pese_al_rollback`: un login fallido
lanza AuthError, y `get_db()` (db/session.py) hace rollback cuando una
excepción sube por el request. Si el registro no se commitea ANTES de
lanzar, se pierde justo la fila que uno quiere auditar — y el bug sería
invisible, porque el login seguiría comportándose igual desde afuera.
"""
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.acceso import Acceso
from app.models.usuario import Usuario


async def _accesos_de(session: AsyncSession, username: str) -> list[Acceso]:
    result = await session.execute(
        select(Acceso).where(Acceso.username == username).order_by(Acceso.id)
    )
    return list(result.scalars().all())


async def _login(client: AsyncClient, username: str, password: str):
    return await client.post(
        "/api/v1/auth/login", data={"username": username, "password": password}
    )


async def test_login_exitoso_queda_registrado(
    client: AsyncClient, db_session: AsyncSession, admin_general_headers: dict[str, str]
):
    # El fixture admin_general_headers ya hizo un login exitoso.
    accesos = await _accesos_de(db_session, "admin_general_test")
    assert len(accesos) == 1
    assert accesos[0].exitoso is True
    assert accesos[0].motivo is None
    assert accesos[0].usuario_id is not None
    assert accesos[0].fecha is not None


async def test_login_fallido_queda_registrado_pese_al_rollback(
    client: AsyncClient, db_session: AsyncSession
):
    """El corazón de esta feature: la contraseña equivocada tiene que
    quedar anotada aunque el request termine en 401 y con rollback."""
    usuario = Usuario(
        username="con_password_malo",
        nombre="Con Password Malo",
        password_hash="$2b$12$abcdefghijklmnopqrstuv",  # hash inválido a propósito
        rol="Arbitro",
    )
    db_session.add(usuario)
    await db_session.commit()
    # Se guarda el id como int ANTES del login: el rollback del request
    # (que este test justamente provoca) expira los objetos ORM de esta
    # sesión, y leer usuario.id después dispararía una recarga.
    usuario_id = usuario.id

    resp = await _login(client, "con_password_malo", "loquesea")
    assert resp.status_code == 401

    accesos = await _accesos_de(db_session, "con_password_malo")
    assert len(accesos) == 1, "el intento fallido se perdió con el rollback del request"
    assert accesos[0].exitoso is False
    assert accesos[0].motivo == "credenciales"
    # Se sabe CONTRA QUÉ cuenta fue el intento, aunque el mensaje que ve el
    # cliente no lo revele — es lo que permite ver "N fallos contra X".
    assert accesos[0].usuario_id == usuario_id


async def test_intento_contra_usuario_inexistente_se_registra_sin_usuario_id(
    client: AsyncClient, db_session: AsyncSession
):
    resp = await _login(client, "no_existe_nadie_asi", "loquesea")
    assert resp.status_code == 401

    accesos = await _accesos_de(db_session, "no_existe_nadie_asi")
    assert len(accesos) == 1
    assert accesos[0].usuario_id is None
    assert accesos[0].motivo == "credenciales"


async def test_usuario_inactivo_se_registra_con_su_propio_motivo(
    client: AsyncClient, db_session: AsyncSession
):
    """'inactivo' se distingue de 'credenciales' a propósito: son dos
    historias distintas para quien audita — alguien adivinando contraseñas
    vs. un ex-empleado intentando entrar con las suyas, que siguen siendo
    correctas."""
    from app.core.security import hash_password

    usuario = Usuario(
        username="dado_de_baja",
        nombre="Dado De Baja",
        password_hash=hash_password("clave-valida-123"),
        rol="Arbitro",
        estado="Inactivo",
    )
    db_session.add(usuario)
    await db_session.commit()
    usuario_id = usuario.id  # ver la nota del test anterior

    resp = await _login(client, "dado_de_baja", "clave-valida-123")
    assert resp.status_code == 401

    accesos = await _accesos_de(db_session, "dado_de_baja")
    assert len(accesos) == 1
    assert accesos[0].motivo == "inactivo"
    assert accesos[0].usuario_id == usuario_id


async def test_nunca_se_guarda_la_password_probada(client: AsyncClient, db_session: AsyncSession):
    """Regresión explícita: ninguna columna de ACCESOS puede terminar
    conteniendo la contraseña, ni siquiera por accidente al agregar un
    campo nuevo a la tabla."""
    secreto = "PasswordSuperSecreta-98765"
    await _login(client, "usuario_fantasma", secreto)

    accesos = await _accesos_de(db_session, "usuario_fantasma")
    assert len(accesos) == 1
    valores = " ".join(str(v) for v in accesos[0].__dict__.values())
    assert secreto not in valores


async def test_se_registra_ip_y_user_agent(client: AsyncClient, db_session: AsyncSession):
    await client.post(
        "/api/v1/auth/login",
        data={"username": "con_headers", "password": "x"},
        headers={"User-Agent": "NavegadorDePrueba/1.0", "X-Forwarded-For": "203.0.113.7, 10.0.0.1"},
    )
    accesos = await _accesos_de(db_session, "con_headers")
    assert len(accesos) == 1
    # El PRIMER valor de X-Forwarded-For (el cliente original), no el proxy.
    assert accesos[0].ip == "203.0.113.7"
    assert accesos[0].user_agent == "NavegadorDePrueba/1.0"


async def test_username_larguisimo_no_rompe_el_registro(
    client: AsyncClient, db_session: AsyncSession
):
    """Un username de 500 caracteres no puede tumbar el login con un 500 ni
    perder la fila: se trunca a lo que aguanta la columna. Y es justo el
    tipo de intento que interesa registrar."""
    largo = "a" * 500
    resp = await _login(client, largo, "x")
    assert resp.status_code == 401

    accesos = await _accesos_de(db_session, largo[:50])
    assert len(accesos) == 1
    assert len(accesos[0].username) == 50


# --- GET /accesos ---


async def test_listar_accesos_exige_admin_general(
    client: AsyncClient, torneo_admin_headers: dict[str, str]
):
    """Más estricto que /usuarios (que TorneoAdmin lee recortado): acá cada
    fila dice quién entró y desde dónde."""
    resp = await client.get("/api/v1/accesos", headers=torneo_admin_headers)
    assert resp.status_code == 403


async def test_listar_accesos_es_privado(client: AsyncClient):
    resp = await client.get("/api/v1/accesos")
    assert resp.status_code == 401


async def test_admin_general_lista_accesos_del_mas_reciente_al_mas_viejo(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    await _login(client, "uno_cualquiera", "x")
    await _login(client, "otro_cualquiera", "x")

    resp = await client.get("/api/v1/accesos", headers=admin_general_headers)
    assert resp.status_code == 200, resp.text
    filas = resp.json()
    assert len(filas) >= 3  # los dos de arriba + el login del fixture
    usernames = [f["username"] for f in filas]
    # El último intento aparece primero.
    assert usernames.index("otro_cualquiera") < usernames.index("uno_cualquiera")


async def test_filtro_por_exitoso_y_por_username(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    await _login(client, "zzz_fallido_filtro", "x")

    resp = await client.get(
        "/api/v1/accesos", params={"exitoso": False}, headers=admin_general_headers
    )
    assert all(f["exitoso"] is False for f in resp.json())

    resp = await client.get(
        "/api/v1/accesos", params={"exitoso": True}, headers=admin_general_headers
    )
    assert all(f["exitoso"] is True for f in resp.json())

    # Coincidencia parcial e insensible a mayúsculas.
    resp = await client.get(
        "/api/v1/accesos", params={"username": "ZZZ_FALLIDO"}, headers=admin_general_headers
    )
    assert [f["username"] for f in resp.json()] == ["zzz_fallido_filtro"]


async def test_filtro_por_fecha_incluye_el_dia_entero(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """`hasta=hoy` tiene que incluir lo que pasó hoy. Si el filtro
    comparara contra la medianoche de ese día, auditar "hasta hoy" no
    devolvería nada del día en curso — el error clásico."""
    from datetime import date

    hoy = date.today().isoformat()
    await _login(client, "de_hoy_mismo", "x")

    resp = await client.get(
        "/api/v1/accesos", params={"desde": hoy, "hasta": hoy}, headers=admin_general_headers
    )
    assert resp.status_code == 200
    assert "de_hoy_mismo" in [f["username"] for f in resp.json()]


async def test_no_existe_forma_de_escribir_ni_borrar_la_bitacora(
    client: AsyncClient, admin_general_headers: dict[str, str]
):
    """Una bitácora con endpoint de escritura o borrado se puede falsificar
    desde afuera. Ni siquiera AdminGeneral debe poder."""
    assert (await client.post("/api/v1/accesos", json={}, headers=admin_general_headers)).status_code == 405
    assert (await client.delete("/api/v1/accesos/1", headers=admin_general_headers)).status_code in (404, 405)


# --- Retención: se borra lo de más de un mes ---


async def test_purga_borra_lo_viejo_y_conserva_lo_reciente(db_session: AsyncSession):
    """El corte es por antigüedad, no "borrar todo": lo de ayer se queda."""
    from datetime import datetime, timedelta

    from app.repositories.acceso import AccesoRepository

    ahora = datetime.now()
    db_session.add_all([
        Acceso(username="viejo_2meses", exitoso=False, motivo="credenciales",
               fecha=ahora - timedelta(days=60)),
        Acceso(username="justo_pasado", exitoso=False, motivo="credenciales",
               fecha=ahora - timedelta(days=31)),
        Acceso(username="justo_adentro", exitoso=False, motivo="credenciales",
               fecha=ahora - timedelta(days=29)),
        Acceso(username="de_ayer", exitoso=True, fecha=ahora - timedelta(days=1)),
    ])
    await db_session.commit()

    borrados = await AccesoRepository(db_session).purgar_anteriores_a(30)
    assert borrados == 2

    quedan = {a.username for a in (await _accesos_de(db_session, "viejo_2meses"))}
    assert quedan == set()
    assert len(await _accesos_de(db_session, "justo_pasado")) == 0
    assert len(await _accesos_de(db_session, "justo_adentro")) == 1
    assert len(await _accesos_de(db_session, "de_ayer")) == 1


async def test_purga_desactivada_no_borra_nada(db_session: AsyncSession):
    """`accesos_retencion_dias = 0` significa "guardar todo". Apagar la
    retención tiene que ser cambiar un número, no comentar código."""
    from datetime import datetime, timedelta

    from app.repositories.acceso import AccesoRepository

    db_session.add(
        Acceso(username="antiquisimo", exitoso=False, motivo="credenciales",
               fecha=datetime.now() - timedelta(days=999))
    )
    await db_session.commit()

    assert await AccesoRepository(db_session).purgar_anteriores_a(0) == 0
    assert len(await _accesos_de(db_session, "antiquisimo")) == 1


async def test_purga_sin_nada_que_borrar_no_falla(db_session: AsyncSession):
    from app.repositories.acceso import AccesoRepository

    assert await AccesoRepository(db_session).purgar_anteriores_a(30) >= 0
