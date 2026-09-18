"""Motor de reglamento de torneo genérico (TODOS.md — decisión tomada
2026-09-17). Centraliza la resolución de los campos de "reglamento del
torneo" que hoy viven como columnas sueltas en `Torneo`
(minimo_jugadores_para_iniciar, maximo_titulares_permitido,
permite_cambios_ilimitados, maximo_cambios_por_equipo,
metodo_desempate_eliminatoria, formato_eliminatoria,
permite_walkover_grupos, cupo_maximo_inscripciones), para que dejen de
reimplementarse por separado en cada consumidor — el fallback
`torneo.X or modalidad.tamano_equipo` estaba escrito dos veces, de forma
independiente, entre HitoPartidoService y ConvocadoAPartidoService, y el
snapshot de desempate entre HitoPartidoService y PartidoService.

Alcance deliberado: NO toca el esquema de DB ni el contrato de API — las
columnas siguen existiendo tal cual en Torneo/TorneoCreate/TorneoUpdate/
TorneoOut. Esto es la capa de dominio que las interpreta, no una
migración.
"""

from dataclasses import dataclass

from app.exceptions.errors import DomainRuleError
from app.models.torneo import Torneo
from app.services.desempate import resolver_metodo_desempate_aplicable


@dataclass(frozen=True)
class ReglamentoTorneo:
    _minimo_jugadores_para_iniciar: int | None
    _maximo_titulares_permitido: int | None
    permite_cambios_ilimitados: bool
    maximo_cambios_por_equipo: int | None
    metodo_desempate_eliminatoria: str
    formato_eliminatoria: str
    permite_walkover_grupos: bool
    cupo_maximo_inscripciones: int | None

    @classmethod
    def desde(cls, torneo: Torneo) -> "ReglamentoTorneo":
        """Envuelve las columnas ya cargadas de `torneo` — no dispara
        ninguna consulta nueva."""
        return cls(
            _minimo_jugadores_para_iniciar=torneo.minimo_jugadores_para_iniciar,
            _maximo_titulares_permitido=torneo.maximo_titulares_permitido,
            permite_cambios_ilimitados=torneo.permite_cambios_ilimitados,
            maximo_cambios_por_equipo=torneo.maximo_cambios_por_equipo,
            metodo_desempate_eliminatoria=torneo.metodo_desempate_eliminatoria,
            formato_eliminatoria=torneo.formato_eliminatoria,
            permite_walkover_grupos=torneo.permite_walkover_grupos,
            cupo_maximo_inscripciones=torneo.cupo_maximo_inscripciones,
        )

    def minimo_titulares(self, tamano_equipo_modalidad: int) -> int:
        """`None` = "exigir el equipo completo" (gestionar-partido-
        alineaciones-plan.md, D1). Un `or` alcanza porque
        chk_torneo_minimo_iniciar prohíbe el 0."""
        return self._minimo_jugadores_para_iniciar or tamano_equipo_modalidad

    def maximo_titulares(self, tamano_equipo_modalidad: int) -> int:
        """`None` = "usar Modalidad.tamano_equipo" (modo-vivo-
        sustituciones-cierre-plan.md, Área 1, T18)."""
        return self._maximo_titulares_permitido or tamano_equipo_modalidad

    def resolver_desempate_aplicable(self, ronda_nombre: str | None) -> str:
        """Snapshot de la regla de desempate al arrancar un partido de
        Eliminación (D6/§8) — mismo cálculo que usan tanto el cronómetro
        en vivo como la carga directa."""
        return resolver_metodo_desempate_aplicable(self.metodo_desempate_eliminatoria, ronda_nombre)


def validar_minimo_para_iniciar(minimo: int | None, modalidad_tamano_equipo: int, modalidad_nombre: str) -> None:
    """Tope superior de Torneo.minimo_jugadores_para_iniciar
    (gestionar-partido-alineaciones-plan.md, D1). El piso (>= 1) lo cubre
    chk_torneo_minimo_iniciar; el techo cruza tablas y vive acá."""
    if minimo is None:
        return
    if minimo > modalidad_tamano_equipo:
        raise DomainRuleError(
            f"El mínimo para iniciar ({minimo}) no puede ser mayor que el tamaño del equipo "
            f"de la modalidad {modalidad_nombre} ({modalidad_tamano_equipo}). "
            "Dejalo vacío para exigir el equipo completo."
        )


def validar_maximo_titulares(maximo: int | None, modalidad_tamano_equipo: int, modalidad_nombre: str) -> None:
    """Tope SUPERIOR de Torneo.maximo_titulares_permitido
    (modo-vivo-sustituciones-cierre-plan.md, Área 1, T18) — mismo criterio
    que validar_minimo_para_iniciar."""
    if maximo is None:
        return
    if maximo > modalidad_tamano_equipo:
        raise DomainRuleError(
            f"El máximo de titulares ({maximo}) no puede ser mayor que el tamaño del equipo "
            f"de la modalidad {modalidad_nombre} ({modalidad_tamano_equipo}). "
            "Dejalo vacío para usar el tamaño de la modalidad."
        )
