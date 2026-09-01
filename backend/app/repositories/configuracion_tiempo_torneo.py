from sqlalchemy import select

from app.models.configuracion_tiempo_torneo import ConfiguracionTiempoTorneo
from app.repositories.base import BaseRepository


class ConfiguracionTiempoTorneoRepository(BaseRepository[ConfiguracionTiempoTorneo]):
    model = ConfiguracionTiempoTorneo
    nombre_recurso = "Configuración de tiempos del torneo"

    async def get_by_torneo(self, torneo_id: int) -> ConfiguracionTiempoTorneo | None:
        """unique_config_tiempo_torneo (02_constraints.sql) — 1:1 con Torneo."""
        stmt = select(ConfiguracionTiempoTorneo).where(ConfiguracionTiempoTorneo.torneo_id == torneo_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def reemplazar(self, config: ConfiguracionTiempoTorneo, **datos) -> ConfiguracionTiempoTorneo:
        """A diferencia de BaseRepository.save_changes (que ignora valores
        None para no pisar campos que un PATCH parcial no mandó), acá el
        payload SIEMPRE viene completo — ConfiguracionTiempoTorneoCreate no
        admite una mezcla a medias (ver su validador de coherencia).
        Cambiar de 'Periodos' a 'Corrido' necesita poder poner
        cantidad_periodos/duracion_periodo_minutos en NULL de verdad, o el
        CHECK cruzado (chk_config_tiempo_periodos) rechaza la fila."""
        for campo, valor in datos.items():
            setattr(config, campo, valor)
        await self.session.commit()
        await self.session.refresh(config)
        return config
