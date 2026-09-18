# TODOS

Todo lo que ya estaba implementado/hecho fue retirado de esta lista el
2026-09-17. El detalle histórico de cada decisión (por qué se hizo así,
alternativas evaluadas, tests) sigue en `docs/plans/*.md` si hace falta
retomarlo — acá solo queda lo que sigue abierto.

## Pendiente — ya evaluado, falta ejecutar

- **Paginación real con cursor en `/equipos` y `/jugadores`** (3B-9). Cambia
  el contrato de API (rompe cualquier cliente que asuma offset) — requiere
  su propio ciclo, no es un fix acotado.
- **Editar el catálogo maestro de disciplinas desde la UI**, no solo por
  migración SQL manual (EC-32 / 3B-11). Toca el `CHECK` de roles y cada
  `require_roles(...)` del código — mismo orden de magnitud que la
  paginación de arriba.
- **Migrar `DetalleEquipo.tsx`/`ModalIndividual`** al `SelectorJugadorBuscable`
  compartido y al hook de resolución de nombres — mejora recomendada dos
  veces, nunca pedida explícitamente.
- **Tests de concurrencia real** (2 conexiones DB genuinamente paralelas)
  para el tope de titulares y el doble `Fin_Partido` (T23/T24). Los tests
  actuales cubren el caso secuencial pero no 2 sesiones simultáneas contra
  la misma fila — requiere infraestructura de test que el repo no tiene
  todavía.
- **Retirar el formulario de Cambio duplicado dentro de `CargaEvento`**
  ahora que existe `ModalSustitucion` — quedó compartiendo la heurística de
  elegibilidad en vez de duplicarla, pero el segundo camino de UI sigue
  vivo. Retirarlo requiere revisar `MesaPanel.test.tsx` con cuidado.
- **Wireframe de 3 zonas** del panel en vivo (Design Fase 2 del plan de Modo
  en Vivo) — nunca se reorganizó el layout en franjas fijas
  primaria/secundaria/terciaria.
- **Row-locking en `EventoPartidoService.create`** (camino en vivo) para 2
  tarjetas simultáneas del mismo jugador — riesgo bajo, gap de concurrencia
  conocido y diferido.
- **Filtrar por asignación los LISTADOS de sub-recursos** dentro de un
  torneo específico (equipos/jugadores/partidos) en `torneo-admin/*` —
  heredan protección de escritura pero no filtran el listado. Prioridad P3.
- **Métricas/alertas de revocación de licencia** (contador otorgadas/
  revocadas por día, alerta de pico de 403 post-revocación). Hoy solo queda
  en `AUDITORIA`, sin dashboard ni alerta activa. Prioridad P3.

## Bloqueado — necesita una respuesta tuya

1. **Notificación por correo al jugador** cuando es traspasado o pasa a
   libre está parada porque falta elegir proveedor de correo (decisión de
   infraestructura). **Pospuesto explícitamente (2026-09-17)** hasta que el
   resto del proyecto esté más afinado.

## Resuelto (2026-09-17)

- **Motor de reglamento de torneo genérico** (`ReglamentoTorneo`) —
  **hecho, alcance Python-only.** Nuevo `app/services/reglamento_torneo.py`
  (dataclass `ReglamentoTorneo` + `validar_minimo_para_iniciar`/
  `validar_maximo_titulares`) unifica la resolución de los 8 campos de
  reglamento de `Torneo`, consumido por `torneo.py`, `hito_partido.py`,
  `convocado_a_partido.py` y `partido.py` — elimina las 2 duplicaciones
  reales encontradas (fallback `torneo.X or modalidad.tamano_equipo` entre
  `HitoPartidoService`/`ConvocadoAPartidoService`, y el snapshot de
  desempate entre `HitoPartidoService`/`PartidoService`). **Esquema de DB,
  contrato de API y frontend sin cambios a propósito** — eso seguiría
  siendo Effort L si algún día se decide (ver el detalle de alcance en
  `~/.claude/plans/optimized-tickling-garden.md` si hace falta retomarlo).
  520 tests backend en verde (incluye 8 nuevos en
  `test_reglamento_torneo.py`); los 7 archivos de tests dedicados a estos
  campos no se tocaron.

- **Fase 3 del desempate de eliminatoria** (tiempo extra como reloj real) —
  se corrió `docs/queries/metricas-desempate-tiempo-extra-penales.sql`
  contra `torneos_mvp` (dev). Resultado: **0 torneos de Eliminación en los
  últimos 30 días, 0 llaves desempatadas, 0 cierres en los últimos 90
  días** — la base de dev no tiene volumen real todavía, así que la
  métrica 4 (el gate, C10) no puede evaluarse por falta de datos, no
  porque domine la carga directa. **Conclusión: seguimos sin poder agendar
  Fase 3 con evidencia real** — no es un "no" definitivo, es "todavía no
  hay señal". Revisitar esta consulta cuando haya partidos de Eliminación
  reales cerrados (torneo en producción/uso real, no solo datos de
  desarrollo).
- **Vista consolidada de estadísticas cruzando ediciones** de un mismo
  `TORNEO_GRUPO` (3B-5) — **regla de negocio confirmada:** las
  estadísticas se cuentan por edición y por equipo tal como se jugaron —
  un jugador que jugó la edición 1 con el Equipo A y la edición 2 con el
  Equipo B aporta a las estadísticas de CADA equipo en SU edición, sin
  fusionar identidad entre ediciones (cada edición tiene sus propios
  equipos). Con esto ya no está bloqueada por diseño — pasa a
  "Backlog sin urgencia" abajo, lista para agendar cuando se pida.

## Backlog sin urgencia (evaluado, nadie lo pidió todavía)

- Clonar la plantilla de una edición a la siguiente (3B-6) — recomendación
  vigente: no construir hasta que se pida.
- Fusionar Modo en Vivo + Resultado Directo en un único motor de eventos —
  requiere antes medir qué fracción de partidos "resultado directo" tiene
  convocatoria guardada (esa métrica no existe hoy).
- Restaurar desde `localStorage` un batch de Resultado Directo no guardado
  tras un refresh accidental.
- `DESIGN.md` formal del proyecto vía `/design-consultation` — recomendado
  por 5 planes consecutivos, nunca ejecutado.
- Sanciones disciplinarias que acumulan tarjetas ENTRE partidos (ej. 3
  amarillas en el torneo = suspensión).
- Palmarés a través de las ediciones de un `TORNEO_GRUPO` — bloqueado por
  las columnas de podio y la página pública de campeón (UC2), ninguna
  existe todavía. Prioridad P3.
- Desempate por llave individual (override puntual de
  `Metodo_Desempate_Eliminatoria` para un solo cruce) — el hook de datos ya
  existe, falta la UI.
- Tanda de penales gol a gol (quién pateó/atajó, en qué orden).
- Unificar la edición de `formato_eliminatoria`/`metodo_desempate` en el
  formulario principal de torneo (hoy es un botón aparte) — cosmético.
- Bracket visual con líneas de conexión del árbol (hoy son columnas sin
  conectar) — trabajo de diseño gráfico, no bloquea funcionalidad.
- Badge visual de sanción pendiente en convocatoria — depende de un modelo
  de "sanciones" que no existe todavía.
- Exportar un resultado directo cargado a texto plano (para WhatsApp).
- Mecanismo genérico de "operación reversible con ventana de gracia" — se
  generaliza si aparece un segundo caso de uso además de
  `deshacer-cierre-forzado`.
- Portal público — pendientes menores, todos con mitigación ya en
  producción: auto-refresh en vivo del feed (hoy hay botón "Recargar"),
  uploader de imágenes para escudos/logos (hoy es URL de texto), preview de
  Open Graph por torneo/partido, `?fecha`/`?disciplina_id` en
  `GET /api/v1/partidos`, parámetro `tz` del feed, flag para forzar la
  barra de disciplinas con una sola activa, envelope de error con código
  estable, minuto en vivo en la fila del feed (hoy solo dice "EN VIVO").

## Descartado a propósito (no reabrir sin evidencia nueva)

- Equipo con roster autoritativo permanente — evaluado y rechazado 2 veces.
- Registro de resultados para disciplinas de marca/tiempo, combate o mente
  (Atletismo, Boxeo, Ajedrez, etc.) — necesita su propio diseño de
  producto, rechazado 2 veces.
- Categorías de peso/cinturón oficiales de una federación.
- eSports (brackets, integración con Riot/Steam).
- Catálogo de categorías etarias/de género (Sub-13, Libre, Femenino...).
- Iconos SVG propios por disciplina (hoy son emoji).
- `UNIQUE (Nombre, Disciplina_ID)` en `EQUIPOS` — rompería datos existentes.
- Importación masiva desde CSV/Excel para el registro por lote.
- Mover `verificar.ps1` a CI (GitHub Actions) — infraestructura nueva.
- Registrar el logout — requeriría una lista de tokens revocados (JWT es
  sin estado del lado del servidor hoy).
- Muerte súbita / gol de oro en el alargue — ninguna competencia real de
  este mercado lo usa.
