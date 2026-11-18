from __future__ import annotations

from datetime import datetime, timedelta
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions.errors import AuthError, ForbiddenError, LicenseRevokedError, NotFoundError, RateLimitError
from app.models.usuario import Usuario
from app.repositories.acceso import AccesoRepository
from app.repositories.asignacion_torneo_admin import AsignacionTorneoAdminRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.auth import Token
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate


@lru_cache
def _hash_de_relleno() -> str:
    """Hash contra el que se verifica cuando la cuenta no existe, para que
    ese caso tarde lo mismo que una contraseña incorrecta (bcrypt es lo
    caro). Sin esto la diferencia de tiempos revela qué usuarios existen
    (TASK-004, SEC-13). Se calcula una vez, en el primer login fallido."""
    return hash_password("hash-de-relleno-para-igualar-tiempos")


class UsuarioService:
    def __init__(self, session: AsyncSession):
        self.repo = UsuarioRepository(session)
        self.acceso_repo = AccesoRepository(session)
        self.asignacion_repo = AsignacionTorneoAdminRepository(session)

    async def get(self, id_: int, usuario_actual: Usuario) -> Usuario:
        usuario = await self.repo.get_or_404(id_)
        # Mismo recorte que list() (D5, roles-3-modulos-plan.md Fase 2):
        # TorneoAdmin solo puede ver cuentas Arbitro. 404 en vez de 403 —
        # no confirma que el id pedido exista si es de otro tipo de cuenta.
        if usuario_actual.rol == "TorneoAdmin" and usuario.rol != "Arbitro":
            raise NotFoundError("Usuario", id_)
        return usuario

    async def list(self, usuario_actual: Usuario, skip: int = 0, limit: int = 100, rol: str | None = None) -> list[Usuario]:
        # D5 (roles-3-modulos-plan.md, Fase 2): GET /usuarios se abrió a
        # TorneoAdmin para que pueda armar el picker de árbitro al asignar
        # un partido, pero solo eso — nunca el roster completo. Se fuerza
        # el filtro acá, en el Service, no en el router: así no depende de
        # que el frontend mande el query param "bien". Cualquier `rol` que
        # TorneoAdmin mande se pisa; AdminGeneral no tiene esta restricción.
        if usuario_actual.rol == "TorneoAdmin":
            rol = "Arbitro"
        return await self.repo.list(skip=skip, limit=limit, rol=rol)

    async def create(self, data: UsuarioCreate) -> Usuario:
        payload = data.model_dump(exclude={"password"})
        payload["password_hash"] = hash_password(data.password)
        return await self.repo.create(**payload)

    async def update(self, id_: int, data: UsuarioUpdate, usuario_actual: Usuario) -> Usuario:
        # Guard de auto-lockout (roles-3-modulos-plan.md, Fase 1, T6): con un
        # solo AdminGeneral hoy, si se cambia su propio rol o se desactiva a
        # sí mismo se queda sin acceso y no hay nadie que lo revierta.
        if id_ == usuario_actual.id:
            if data.rol is not None and data.rol != usuario_actual.rol:
                raise ForbiddenError("No podés cambiar tu propio rol.")
            if data.estado == "Inactivo":
                raise ForbiddenError("No podés desactivar tu propia cuenta.")
        payload = data.model_dump(exclude_unset=True, exclude={"password"})
        if data.password is not None:
            payload["password_hash"] = hash_password(data.password)

        objetivo = await self.repo.get_or_404(id_)
        rol_anterior = objetivo.rol
        usuario = await self.repo.save_changes(objetivo, **payload)

        # Asignaciones huérfanas (rbac-licencias-torneos-plan.md, §3.2,
        # hallazgo #3 de la voz externa Eng): fn_validar_asignacion_torneo_admin_rol
        # (06_triggers.sql) solo valida al INSERT/UPDATE de la fila de
        # asignación, no cuando el USUARIO cambia de rol después. Sin
        # esto, degradar un TorneoAdmin deja sus filas Activo huérfanas —
        # si se lo re-promueve más adelante, resucitan accesos que ningún
        # AdminGeneral decidió conscientemente en ese momento.
        if rol_anterior == "TorneoAdmin" and usuario.rol != "TorneoAdmin":
            await self.asignacion_repo.desactivar_todas_del_usuario(id_)

        return usuario

    async def soft_delete(self, id_: int, usuario_actual: Usuario) -> Usuario:
        if id_ == usuario_actual.id:
            raise ForbiddenError("No podés desactivar tu propia cuenta.")
        return await self.repo.soft_delete(id_, estado_inactivo="Inactivo")

    async def bootstrap_admin_si_no_existe(
        self, username: str, password: str, nombre: str
    ) -> Usuario | None:
        """Crea el primer Admin si la tabla usuarios está vacía.

        No hay seed de usuarios en /database (05_seed.sql no los toca: las
        contraseñas no se versionan en SQL), así que sin esto no habría forma
        de loguearse la primera vez sin tocar la base a mano.
        """
        if await self.repo.count() > 0:
            return None
        return await self.repo.create(
            username=username.strip().lower(),
            nombre=nombre,
            password_hash=hash_password(password),
            rol="AdminGeneral",
        )

    async def login(
        self,
        username: str,
        password: str,
        ip: str | None = None,
        user_agent: str | None = None,
    ) -> Token:
        """Autentica y deja constancia del intento en ACCESOS, salga bien o mal.

        El orden de las operaciones importa y no es negociable: el registro
        se COMMITEA antes de lanzar AuthError. `get_db()` (db/session.py)
        hace `rollback()` cuando una excepción sube por el request, así que
        anotar el fallo y lanzar sin commitear de por medio borraría
        exactamente la fila que más interesa auditar. Un commit ya hecho no
        lo revierte ese rollback posterior.

        Si el INSERT de auditoría falla, el login falla con él (no se
        atrapa la excepción). Es deliberado: un fallo escribiendo acá
        significa que la base no está respondiendo, y en ese estado el
        login tampoco podría verificar credenciales — tragarse el error
        solo cambiaría un 500 honesto por un agujero silencioso en la
        bitácora.

        `ip` y `user_agent` los pasa el router desde el Request; son
        opcionales para que un llamador interno (o un test que no le
        importa) no tenga que fabricarlos.

        3B-14 (docs/plans/cierre-backlog-todos-plan.md): antes de tocar la
        base para resolver el usuario, chequea el rate limit por
        (username, IP) — ver AccesoRepository.contar_fallos_credenciales_recientes
        para por qué el par y no uno solo. El chequeo va PRIMERO (no
        después de resolver `usuario`) para no gastar ni esa consulta en
        un intento ya bloqueado, y para que el mensaje/motivo sea idéntico
        exista o no la cuenta — no filtra más de lo que 'credenciales' ya
        filtra."""
        # TASK-004 (SEC-01): el mismo valor para contar, buscar la cuenta y
        # registrar el acceso. Antes el contador usaba el texto tal como
        # llegaba y la búsqueda lo normalizaba: 'admin', 'ADMIN' y 'admin '
        # eran la misma cuenta con contadores separados. El recorte a 50 es
        # el de la columna ACCESOS.Username (ver _registrar_acceso): contar
        # con otro largo que el guardado no encontraría nunca las filas.
        username = username.strip().lower()[:50]

        settings = get_settings()
        if settings.login_rate_limit_intentos > 0 and settings.login_rate_limit_ventana_minutos > 0:
            desde = datetime.now() - timedelta(minutes=settings.login_rate_limit_ventana_minutos)
            fallos = await self.acceso_repo.contar_fallos_credenciales_recientes(username, ip, desde)
            # Tope por cuenta, sin importar la IP (TASK-004): frena un ataque
            # repartido entre muchas IPs, que por (usuario, IP) nunca llega
            # al umbral.
            tope_cuenta = settings.login_rate_limit_intentos_cuenta
            fallos_cuenta = (
                await self.acceso_repo.contar_fallos_credenciales_recientes(username, None, desde)
                if tope_cuenta > 0
                else 0
            )
            if fallos >= settings.login_rate_limit_intentos or (tope_cuenta > 0 and fallos_cuenta >= tope_cuenta):
                await self._registrar_acceso(
                    usuario_id=None,
                    username=username,
                    exitoso=False,
                    motivo="bloqueado",
                    ip=ip,
                    user_agent=user_agent,
                )
                raise RateLimitError(
                    "Demasiados intentos fallidos. Esperá unos minutos antes de volver a intentar.",
                    retry_after_seconds=settings.login_rate_limit_ventana_minutos * 60,
                )

        usuario = await self.repo.get_by_username(username)

        # Con la cuenta inexistente también se verifica un hash: ver
        # _hash_de_relleno.
        hash_a_verificar = usuario.password_hash if usuario is not None else _hash_de_relleno()
        if not verify_password(password, hash_a_verificar) or usuario is None:
            # usuario_id queda en None cuando el username no existe; cuando
            # existe pero la contraseña no coincide, SÍ se anota el id — es
            # lo que permite ver "3 fallos seguidos contra la cuenta X".
            # Hacia afuera el mensaje es el mismo en los dos casos, para no
            # revelar qué usernames existen.
            await self._registrar_acceso(
                usuario_id=usuario.id if usuario else None,
                username=username,
                exitoso=False,
                motivo="credenciales",
                ip=ip,
                user_agent=user_agent,
            )
            raise AuthError("Usuario o contraseña incorrectos.")

        if usuario.estado != "Activo":
            await self._registrar_acceso(
                usuario_id=usuario.id,
                username=username,
                exitoso=False,
                motivo="inactivo",
                ip=ip,
                user_agent=user_agent,
            )
            raise AuthError("El usuario está inactivo.")

        # Licencia (rbac-licencias-torneos-plan.md, D2a): kill switch de
        # nivel superior, chequeado acá igual que en get_current_user —
        # sin este bloque, un login con licencia revocada desaparecería
        # silenciosamente de la bitácora de ACCESOS en vez de quedar
        # registrado como motivo='licencia_revocada' (hallazgo de la voz
        # externa, Eng review). Mismo orden que 'inactivo': el registro
        # de acceso se escribe ANTES de lanzar, no después.
        if not usuario.licencia_activa:
            await self._registrar_acceso(
                usuario_id=usuario.id,
                username=username,
                exitoso=False,
                motivo="licencia_revocada",
                ip=ip,
                user_agent=user_agent,
            )
            raise LicenseRevokedError()

        await self._registrar_acceso(
            usuario_id=usuario.id,
            username=usuario.username,
            exitoso=True,
            motivo=None,
            ip=ip,
            user_agent=user_agent,
        )
        token = create_access_token(subject=usuario.username, rol=usuario.rol)
        return Token(access_token=token, rol=usuario.rol)

    async def _registrar_acceso(
        self,
        usuario_id: int | None,
        username: str,
        exitoso: bool,
        motivo: str | None,
        ip: str | None,
        user_agent: str | None,
    ) -> None:
        """Nunca recibe la contraseña — ver el docstring de models/acceso.py.

        Los recortes son a lo que aguantan las columnas: `username` es el
        texto que mandó el cliente (puede venir de cualquier largo, incluso
        de alguien probando un buffer largo a propósito) y el `User-Agent`
        de un navegador real ya roza los 200 caracteres. Truncar es
        preferible a perder la fila entera por un error de largo, que es lo
        que pasaría justo en el intento que valía la pena registrar."""
        await self.acceso_repo.create(
            usuario_id=usuario_id,
            username=username[:50],
            exitoso=exitoso,
            motivo=motivo,
            ip=ip[:45] if ip else None,
            user_agent=user_agent[:255] if user_agent else None,
        )

