from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions.errors import AuthError, ForbiddenError, NotFoundError
from app.models.usuario import Usuario
from app.repositories.acceso import AccesoRepository
from app.repositories.usuario import UsuarioRepository
from app.schemas.auth import Token
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate


class UsuarioService:
    def __init__(self, session: AsyncSession):
        self.repo = UsuarioRepository(session)
        self.acceso_repo = AccesoRepository(session)

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
        return await self.repo.update(id_, **payload)

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
        """
        usuario = await self.repo.get_by_username(username)

        if usuario is None or not verify_password(password, usuario.password_hash):
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
