# Pendientes

Estado al 2026-11-20. Lo abierto del proyecto, en orden de importancia:
primero lo que espera una decisión tuya, después lo que se puede hacer ya y
al final lo que no tiene urgencia o se descartó a propósito.

Lo ya resuelto está en [`docs/historial-resueltos.md`](docs/historial-resueltos.md);
varios comentarios del código citan "TODOS.md" por una decisión que hoy
vive ahí.

## Resumen

| Estado | Qué | Detalle |
|---|---|---|
| Espera tu decisión | Despliegue a producción: Fase 5 del roadmap (TASK-049 a 054 y 056) | Dónde se despliega, dominio para HTTPS, destino de las copias |
| Espera tu decisión | Correo al jugador al ser traspasado o quedar libre | Elegir proveedor de correo |
| Se puede hacer ya | Filtrar por torneo asignado los listados internos de `torneo-admin` | P3 |
| Se puede hacer ya | Revisión humana: seguir el README desde cero en una máquina limpia | Criterio de TASK-055; el ensayo automático pasó |
| Diferido con umbral | Paginación con cursor en `/equipos` y `/jugadores` | Se reabre con >150 registros reales o p95 >800 ms |
| Diferido con umbral | Editar el catálogo de disciplinas desde la interfaz | Se reabre al segundo pedido real |

El backlog de la auditoría (`docs/audit/11_BACKLOG_IMPLEMENTACION.md`) está
completo salvo la Fase 5.

## Bloqueado — necesita una respuesta tuya

1. **Notificación por correo al jugador** cuando es traspasado o pasa a
   libre está parada porque falta elegir proveedor de correo (decisión de
   infraestructura). **Pospuesto explícitamente (2026-09-17)** hasta que el
   resto del proyecto esté más afinado.
2. **Despliegue a producción (Fase 5 del roadmap de `docs/audit/`):**
   TASK-049 (imagen del frontend, proxy inverso con TLS), TASK-050
   (configuración por entorno y secretos), TASK-051 (copias automáticas y
   restauración ensayada), TASK-052 (observabilidad), y después 053, 054 y
   056. Falta definir dónde se despliega, el dominio para HTTPS y el
   destino de las copias. **Pospuesto (2026-11-19)** hasta tener esas
   definiciones; el resto del roadmap sigue sin esperar.

## Pendiente — ya evaluado, falta ejecutar

- **Paginación con cursor en `/equipos` y `/jugadores`** (3B-9). TASK-039 ya
  pagina las grillas por desplazamiento (`skip`/`limit` + `X-Total-Count`,
  pie "1–50 de 312") y busca en el servidor; lo que queda diferido es pasar
  a cursor, que cambia el contrato de API. **Diferido con umbral numérico**
  (revisión del plan de cierre, 2026-09-18) — se reabre con (a) >150 equipos
  orgánicos o >150 jugadores orgánicos (75% del tope de página de 200), o
  (b) p95 medido >800ms en `GET /jugadores` o `GET /equipos`, o (c) un
  segundo cliente de la API que no sea este frontend. Hoy: 10 equipos y 37
  jugadores orgánicos (separados de los datos sintéticos de
  `backend/scripts/mock_estres_catalogo.py`, ver `docs/queries/README.md`).
- **Editar el catálogo maestro de disciplinas desde la UI**, no solo por
  migración SQL manual (EC-32 / 3B-11). **Diferido** — se reabre al SEGUNDO
  pedido real de alta de una disciplina fuera del catálogo de 28 (el
  primero se atiende con el script de migración que ya existe). Si se
  reabre: gatear `POST`/`PUT /disciplinas` a `AdminGeneral` (el toggle de
  `Estado` se queda en `TorneoAdmin`, son poderes distintos — no mezclar
  dos niveles de rol en la misma ruta); `Slug` no se edita desde la UI
  (lo consume el portal público); no se agrega un rol nuevo, `AdminGeneral`
  ya alcanza.
- **Filtrar por asignación los LISTADOS de sub-recursos** dentro de un
  torneo específico (equipos/jugadores/partidos) en `torneo-admin/*` —
  heredan protección de escritura pero no filtran el listado. Prioridad P3.
  Si se reabre: el alcance NO se expresa como query param elegible por el
  cliente (invierte el default seguro) — se deriva implícito del token vía
  `torneo_ids_permitidos` (mismo patrón que ya usan `torneos`/`partidos`).
  Un caso de alta/búsqueda que necesite ver filas no inscritas se expresa
  como flag de capacidad con nombre honesto (`incluir_no_inscritos=true`),
  nunca ampliando el techo de permisos del rol.

## Backlog sin urgencia (evaluado, nadie lo pidió todavía)

- Clonar la plantilla de una edición a la siguiente (3B-6) — recomendación
  vigente: no construir hasta que se pida.
- Fusionar Modo en Vivo + Resultado Directo en un único motor de eventos —
  requiere antes medir qué fracción de partidos "resultado directo" tiene
  convocatoria guardada (esa métrica no existe hoy).
- Restaurar desde `localStorage` un batch de Resultado Directo no guardado
  tras un refresh accidental.
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
- Registrar el logout — requeriría una lista de tokens revocados (JWT es
  sin estado del lado del servidor hoy).
- Muerte súbita / gol de oro en el alargue — ninguna competencia real de
  este mercado lo usa.
