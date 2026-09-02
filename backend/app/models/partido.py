from datetime import datetime

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.database import Base
from app.models.mixins import TimestampMixin


class Partido(TimestampMixin, Base):
    __tablename__ = "partidos"

    id: Mapped[int] = mapped_column(primary_key=True)
    torneo_id: Mapped[int] = mapped_column(ForeignKey("torneo.id"))
    # Nullable (Decisión Eng #13, motor-formatos-plantillas-navegacion-
    # plan.md): un partido de ronda 2+ de un bracket de Eliminación se
    # crea ANTES de saber quién lo juega ("Ganador Partido N") — nace con
    # ambos NULL, fn_propagar_ganador_bracket los completa cuando el
    # partido anterior termina.
    equipos_id_local: Mapped[int | None] = mapped_column(ForeignKey("equipos.id"))
    equipos_id_visitante: Mapped[int | None] = mapped_column(ForeignKey("equipos.id"))
    fecha_partido: Mapped[datetime]
    jornada: Mapped[int | None]
    # Fase/Grupo (texto libre) — alta manual ya existente (PartidosAdmin).
    # El motor de formatos nuevo escribe fase_id/grupo_id en su lugar; ver
    # comentario grande en 01_schema.sql sobre por qué conviven.
    # Valores válidos: Regular, Grupos, Octavos, Cuartos, Semifinal, Final, Tercer puesto
    fase: Mapped[str] = mapped_column(String(30), default="Regular")
    grupo: Mapped[str | None] = mapped_column(String(10))
    # Motor de Formatos (requerimiento #4) — estructura real.
    fase_id: Mapped[int | None] = mapped_column(ForeignKey("fase.id"))
    grupo_id: Mapped[int | None] = mapped_column(ForeignKey("grupo.id"))
    # "Octavos de Final", "Semifinal", "Tercer Lugar"... — denormalizado al
    # sortear el bracket, no se recalcula con lógica del cliente.
    ronda_nombre: Mapped[str | None] = mapped_column(String(30))
    # Encadenamiento de bracket: a qué partido avanza el GANADOR.
    partido_siguiente_id: Mapped[int | None] = mapped_column(ForeignKey("partidos.id"))
    # Valores válidos: Local, Visitante (chk_partidos_slot_siguiente)
    slot_siguiente: Mapped[str | None] = mapped_column(String(10))
    # Partido por el 3er/4to lugar (confirmado en el plan): a qué partido
    # avanza el PERDEDOR — solo las 2 semifinales lo usan.
    partido_perdedor_siguiente_id: Mapped[int | None] = mapped_column(ForeignKey("partidos.id"))
    slot_perdedor_siguiente: Mapped[str | None] = mapped_column(String(10))
    # Desempate manual (penales/tiempo extra/decisión arbitral) para un
    # partido de Eliminación empatado en goles — el sistema registra QUIÉN
    # ganó, no CÓMO (mismo nivel de detalle que TRASPASOS.Motivo).
    ganador_desempate_id: Mapped[int | None] = mapped_column(ForeignKey("equipos.id"))
    # Ganador de un partido "Corrido" (Tenis/Pádel — sin marcador de goles).
    # Distinta de ganador_desempate_id: ver el comentario grande en
    # 01_schema.sql sobre por qué no se reusa esa columna.
    ganador_corrido_id: Mapped[int | None] = mapped_column(ForeignKey("equipos.id"))
    # Árbitro asignado a este partido (nullable — puede no tener uno
    # todavía). Un solo árbitro por partido a propósito, ver D6 en
    # roles-3-modulos-plan.md. Usado por el ownership-check de
    # PartidoService/EventoPartidoService (D5).
    arbitro_id: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
    # Valores válidos: Programado, En curso, Finalizado, Cancelado
    estado: Mapped[str] = mapped_column(String(20), default="Programado")
    # Walkover/retiro (3B-13, docs/plans/cierre-backlog-todos-plan.md):
    # marca un partido cerrado por ausencia, no por juego real — 3-0 fijo
    # a favor del presente (vw_resultados_partidos lo aplica). Ver el
    # comentario completo en 01_schema.sql.
    es_walkover: Mapped[bool] = mapped_column(default=False)
    walkover_equipo_ausente_id: Mapped[int | None] = mapped_column(ForeignKey("equipos.id"))
