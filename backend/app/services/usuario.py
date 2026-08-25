from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password, verify_password
from app.exceptions.errors import AuthError
from app.models.usuario import Usuario
from app.repositories.usuario import UsuarioRepository
from app.schemas.auth import Token
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate


class UsuarioService:
    def __init__(self, session: AsyncSession):
        self.repo = UsuarioRepository(session)

    async def get(self, id_: int) -> Usuario:
        return await self.repo.get_or_404(id_)

    async def list(self, skip: int = 0, limit: int = 100, rol: str | None = None) -> list[Usuario]:
        return await self.repo.list(skip=skip, limit=limit, rol=rol)

    async def create(self, data: UsuarioCreate) -> Usuario:
        payload = data.model_dump(exclude={"password"})
        payload["password_hash"] = hash_password(data.password)
        return await self.repo.create(**payload)

    async def update(self, id_: int, data: UsuarioUpdate) -> Usuario:
        payload = data.model_dump(exclude_unset=True, exclude={"password"})
        if data.password is not None:
            payload["password_hash"] = hash_password(data.password)
        return await self.repo.update(id_, **payload)

    async def soft_delete(self, id_: int) -> Usuario:
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
            rol="Admin",
        )

    async def login(self, username: str, password: str) -> Token:
        usuario = await self.repo.get_by_username(username)
        if usuario is None or not verify_password(password, usuario.password_hash):
            raise AuthError("Usuario o contraseña incorrectos.")
        if usuario.estado != "Activo":
            raise AuthError("El usuario está inactivo.")
        token = create_access_token(subject=usuario.username, rol=usuario.rol)
        return Token(access_token=token, rol=usuario.rol)
