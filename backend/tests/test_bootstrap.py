"""bootstrap_admin_si_no_existe (app/main.py lo llama al arrancar) nunca se
ejercita vía HTTP en esta suite: ASGITransport no dispara el lifespan de la
app (ver el comentario en test_auth.py). Se prueba directo contra el
Service, sin cliente HTTP."""
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.usuario import UsuarioService


async def test_bootstrap_admin_si_no_existe_crea_admin_general(db_session: AsyncSession):
    # roles-3-modulos-plan.md, Fase 1, T6: el bug que encontró la voz
    # externa era justo este — bootstrap hardcodeaba rol="Admin", que el
    # CHECK constraint nuevo rechaza.
    usuario = await UsuarioService(db_session).bootstrap_admin_si_no_existe(
        "bootstrap_test", "clave12345", "Bootstrap Test"
    )
    assert usuario is not None
    assert usuario.rol == "AdminGeneral"
    assert usuario.username == "bootstrap_test"


async def test_bootstrap_admin_si_no_existe_no_hace_nada_si_ya_hay_usuarios(
    db_session: AsyncSession,
):
    primero = await UsuarioService(db_session).bootstrap_admin_si_no_existe(
        "primero_test", "clave12345", "Primero"
    )
    assert primero is not None

    segundo = await UsuarioService(db_session).bootstrap_admin_si_no_existe(
        "segundo_test", "clave12345", "Segundo"
    )
    assert segundo is None
