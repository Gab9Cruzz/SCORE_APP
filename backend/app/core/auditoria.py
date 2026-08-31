"""Auditoría de cambios (tabla AUDITORIA): "cualquier cambio queda
registrado" — alta, modificación o baja de CUALQUIER entidad del sistema,
no solo de las que pasan por `BaseRepository`.

Por qué un event listener de sesión de SQLAlchemy y no un hook en
`BaseRepository.create()`/`save_changes()`: varios services (
`motor_formatos`, `traspaso`, `inscripcion_torneo`, `registro_lote`) mutan
objetos con `session.add()`/`setattr()` directo, sin pasar por esos dos
métodos — un hook ahí adentro se perdería justo esas escrituras (fixtures,
sorteos, traspasos, inscripciones en lote). `before_flush`/
`after_flush_postexec` ven TODO lo que el ORM está por escribir en el
flush, venga de donde venga, así que es el único lugar que puede prometer
el "100%" que se pidió. Es, además, el patrón que la propia documentación
de SQLAlchemy usa para "history tracking" (`examples/versioned_history`).

Dos eventos, no uno, por un detalle de timing:

- En `before_flush` los objetos NUEVOS (INSERT) todavía no tienen `id` —
  lo asigna el SERIAL de Postgres recién al ejecutar el INSERT — pero es
  el ÚNICO momento en que `attr.history` todavía tiene el antes Y el
  después de un UPDATE (después del flush, SQLAlchemy ya lo dio por hecho
  y la history se resetea). Acá solo se TOMA LA FOTO: se guarda en
  `session.info`, el dict que SQLAlchemy reserva justo para que un
  listener pase estado de un evento a otro del mismo flush.
- `after_flush_postexec` corre después de que el INSERT/UPDATE ya se
  ejecutó (los `id` autogenerados YA están asignados) pero antes del
  COMMIT. Ahí se arman las filas finales y se insertan con Core
  (`session.execute(insert(...))`, no `session.add()`): es una sentencia
  SQL más sobre la misma conexión/transacción del flush en curso, no un
  objeto nuevo que dispare otro ciclo de unit-of-work — así se evita
  cualquier recursión hacia `before_flush` y la fila de auditoría queda
  atómica con el cambio que audita (si el cambio de negocio no llega a
  commitear, tampoco lo hace su auditoría).
"""
from __future__ import annotations

import contextvars
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Any

from sqlalchemy import event, insert, inspect
from sqlalchemy.orm import Session

from app.models.auditoria import Auditoria

# Tablas que llevan su propia bitácora aparte (ACCESOS, con su propio
# esquema y su propia pantalla) o que SON la bitácora — auditar cada
# intento de login acá lo duplicaría por otro canal, y auditar la propia
# tabla AUDITORIA es ruido, no dato.
_TABLAS_EXCLUIDAS = {"auditoria", "accesos"}

# tabla -> columnas que no pueden quedar en texto plano en una bitácora de
# auditoría. Mismo criterio que ya rige para la contraseña probada en el
# login (ver models/acceso.py): se anota QUE cambió, nunca el valor.
_CAMPOS_REDACTADOS: dict[str, set[str]] = {"usuarios": {"password_hash"}}

# Metadata de la propia fila, no "el cambio": fecha_modificacion cambia en
# TODO update por definición (la pisa un trigger de Postgres, ni siquiera
# pasa por Python) — registrarla no dice nada que Auditoria.fecha no diga
# ya, solo agrega ruido a cada diff.
_COLUMNAS_IGNORADAS = {"fecha_registro", "fecha_modificacion"}

_CLAVE_PENDIENTES = "_auditoria_pendiente"


@dataclass(frozen=True)
class ActorAuditoria:
    usuario_id: int | None
    ip: str | None
    user_agent: str | None


_actor_ctx: contextvars.ContextVar[ActorAuditoria | None] = contextvars.ContextVar(
    "actor_auditoria", default=None
)


def set_actor(usuario_id: int | None, ip: str | None = None, user_agent: str | None = None) -> None:
    """La llama `api/deps.py` en cuanto resuelve el usuario autenticado del
    request (`get_current_user`). `contextvars` aísla esto por request —
    cada uno corre en su propia Task de asyncio, así que no hay forma de
    que un request vea el actor de otro corriendo en paralelo — y evita
    tener que pasar `usuario_actual` a mano por los ~18 repositorios."""
    _actor_ctx.set(ActorAuditoria(usuario_id=usuario_id, ip=ip, user_agent=user_agent))


def _actor_actual() -> ActorAuditoria:
    return _actor_ctx.get() or ActorAuditoria(usuario_id=None, ip=None, user_agent=None)


def _valor_serializable(valor: Any) -> Any:
    """JSONB acepta nativamente str/int/float/bool/None/dict/list; todo lo
    demás que puede aparecer en una columna de este esquema (fechas,
    Enums de Python) necesita conversión explícita o psycopg falla al
    serializar."""
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Decimal):
        return float(valor)
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, (str, int, float, bool)) or valor is None:
        return valor
    return str(valor)


def _es_auditable(obj: Any) -> bool:
    tabla = getattr(obj, "__tablename__", None)
    return tabla is not None and tabla not in _TABLAS_EXCLUIDAS


def _snapshot_completo(obj: Any) -> dict[str, Any]:
    """Todas las columnas de `obj`, para el caso 'crear' — ahí no hay
    'antes' con qué comparar, así que se registra el estado inicial
    completo (menos lo redactado/ignorado)."""
    tabla = obj.__tablename__
    redactadas = _CAMPOS_REDACTADOS.get(tabla, set())
    columnas = {c.key for c in inspect(obj).mapper.column_attrs}
    resultado: dict[str, Any] = {}
    for nombre in columnas - _COLUMNAS_IGNORADAS:
        resultado[nombre] = "(redactado)" if nombre in redactadas else _valor_serializable(getattr(obj, nombre))
    return resultado


@event.listens_for(Session, "before_flush")
def _before_flush(session: Session, flush_context: Any, instances: Any) -> None:
    pendientes: list[dict[str, Any]] = session.info.setdefault(_CLAVE_PENDIENTES, [])

    for obj in list(session.new):
        if not _es_auditable(obj):
            continue
        pendientes.append({
            "obj": obj,
            "tabla": obj.__tablename__,
            "accion": "crear",
            "datos_anteriores": None,
            "datos_nuevos": _snapshot_completo(obj),
        })

    for obj in list(session.dirty):
        if not _es_auditable(obj) or not session.is_modified(obj, include_collections=False):
            continue
        estado = inspect(obj)
        cambiadas = {
            attr.key for attr in estado.mapper.column_attrs if estado.attrs[attr.key].history.has_changes()
        } - _COLUMNAS_IGNORADAS
        if not cambiadas:
            continue

        # BaseRepository.soft_delete marca este atributo transiente justo
        # antes de mutar el objeto (ver repositories/base.py) — es la única
        # forma de distinguir "se dio de baja" de "se modificó cualquier
        # otra cosa" sin adivinar por el nombre/valor de la columna que
        # cambió (Estado también cambia en transiciones de negocio
        # normales, ej. Torneo -> 'Finalizado', que no son una baja).
        accion = getattr(obj, "_auditoria_accion", "modificar")
        if hasattr(obj, "_auditoria_accion"):
            del obj._auditoria_accion

        redactadas = _CAMPOS_REDACTADOS.get(obj.__tablename__, set())
        antes: dict[str, Any] = {}
        despues: dict[str, Any] = {}
        for nombre in cambiadas:
            if nombre in redactadas:
                antes[nombre] = despues[nombre] = "(redactado)"
                continue
            historia = estado.attrs[nombre].history
            valor_antes = historia.deleted[0] if historia.deleted else None
            valor_despues = historia.added[0] if historia.added else getattr(obj, nombre)
            antes[nombre] = _valor_serializable(valor_antes)
            despues[nombre] = _valor_serializable(valor_despues)

        pendientes.append({
            "obj": obj,
            "tabla": obj.__tablename__,
            "accion": accion,
            "datos_anteriores": antes,
            "datos_nuevos": despues,
        })

    for obj in list(session.deleted):
        # Hoy nadie en la app hace un DELETE físico vía ORM (ver el
        # docstring de BaseRepository: es borrado lógico siempre). Se cubre
        # de todas formas para que, si alguna vez aparece uno, no quede
        # afuera de la auditoría en silencio.
        if not _es_auditable(obj):
            continue
        pendientes.append({
            "obj": obj,
            "tabla": obj.__tablename__,
            "accion": "eliminar",
            "datos_anteriores": _snapshot_completo(obj),
            "datos_nuevos": None,
        })


@event.listens_for(Session, "after_flush_postexec")
def _after_flush_postexec(session: Session, context: Any) -> None:
    pendientes = session.info.pop(_CLAVE_PENDIENTES, None)
    if not pendientes:
        return

    actor = _actor_actual()
    filas = []
    for item in pendientes:
        registro_id = getattr(item["obj"], "id", None)
        if registro_id is None:
            # No debería pasar (las 18 tablas de negocio usan `id` como PK
            # simple), pero una fila de auditoría que no apunta a nada no
            # sirve — se descarta en vez de forzar un NULL.
            continue
        filas.append({
            "tabla": item["tabla"],
            "registro_id": registro_id,
            "accion": item["accion"],
            "datos_anteriores": item["datos_anteriores"],
            "datos_nuevos": item["datos_nuevos"],
            "usuario_id": actor.usuario_id,
            "ip": actor.ip[:45] if actor.ip else None,
            "user_agent": actor.user_agent[:255] if actor.user_agent else None,
        })

    if filas:
        session.execute(insert(Auditoria), filas)
