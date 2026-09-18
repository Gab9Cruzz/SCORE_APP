/** Catálogo de tipos de evento, compartido entre el panel en vivo
 * (`MesaPanel`) y la carga de resultado directo (`ModalResultadoDirecto`).
 *
 * Vivía duplicado dentro de `ControlDeMesa.tsx` cuando los dos componentes
 * estaban en el mismo archivo; al partirlo se extrajo acá en vez de copiarlo,
 * para que agregar un tipo de evento siga siendo un cambio en un solo lugar.
 *
 * Los emoji no son decoración: son el vocabulario visual del dominio que la
 * mesa ya usa para cargar sucesos de un toque.
 */
export type TipoEvento = "Gol" | "Autogol" | "Tarjeta Amarilla" | "Tarjeta Roja" | "Cambio";

export const TIPOS: TipoEvento[] = ["Gol", "Autogol", "Tarjeta Amarilla", "Tarjeta Roja", "Cambio"];

export const TIPO_ICONO: Record<TipoEvento, string> = {
  Gol: "⚽",
  Autogol: "⚽ (en contra)",
  "Tarjeta Amarilla": "🟨",
  "Tarjeta Roja": "🟥",
  Cambio: "🔄",
};

/** Una fila de la plantilla vigente tal como la devuelve `GET /plantillas`. */
export interface PlantillaJugador {
  jugador_id: number;
  jugador: string;
  equipo_id: number;
  equipo: string;
  dorsal: number | null;
  jugador_perfil_id: number;
}

interface EventoRegistradoMinimo {
  jugador_id: number;
  jugador_id_entra: number | null;
  eventos_id: number;
}

/** Derivación de "quién sigue disponible" a partir del historial del
 * partido (modo-vivo-sustituciones-cierre-plan.md, Sección 5 — extraído
 * acá para que `CargaEvento` (MesaPanel.tsx) y `ModalSustitucion` compartan
 * el mismo cálculo en vez de que cada uno reimplemente su propia
 * heurística: exactamente el riesgo DRY que el plan señala). Es
 * "plantilla vigente menos quien ya salió o fue expulsado" — para
 * distinguir titular/suplente, ver `deriveTitularSuplente` abajo
 * (goles-por-marcador-slots-plan.md, Fase 3 Eng, corrección 4 — antes vivía
 * mezclado en un solo set negado acá mismo, ambiguo de polaridad entre
 * "Sale" y "Entra"). La validación AUTORITATIVA (tope de cambios,
 * no-retorno, doble-salida) es 100% del backend
 * (`app/services/reglas_cambio.py::validar_reglas_cambio`) — esto es solo
 * la lista de candidatos que se le ofrece al operador.
 *
 * Nombre `derive*` (no `calcular*`): comunica explícitamente "esto es un
 * cálculo puro sobre datos existentes, no una fuente de verdad propia" —
 * mismo criterio de nombrado que `calcular_minuto_actual` en el backend. */
export function deriveHistorialElegibilidad(eventosRegistrados: EventoRegistradoMinimo[], eventoNombrePorId: Map<number, string>) {
  const salidosOExpulsados = new Set<number>();
  for (const e of eventosRegistrados) {
    const nombreTipo = eventoNombrePorId.get(e.eventos_id);
    if (nombreTipo === "Tarjeta Roja" || nombreTipo === "Cambio") salidosOExpulsados.add(e.jugador_id);
  }
  const yaEntraron = new Set(
    eventosRegistrados
      .filter((e) => eventoNombrePorId.get(e.eventos_id) === "Cambio" && e.jugador_id_entra !== null)
      .map((e) => e.jugador_id_entra as number),
  );
  return { salidosOExpulsados, yaEntraron };
}

/** Deriva quiénes son titulares/suplentes AHORA, a partir de la
 * convocatoria guardada (goles-por-marcador-slots-plan.md, Fase 3 Eng,
 * corrección 4). Devuelve los DOS sets EXPLÍCITOS — nunca 1 set negado —
 * para que cada consumidor use el que le corresponde sin ambigüedad de
 * polaridad ("Sale" necesita `titulares`, "Entra" necesita `suplentes`).
 *
 * `convocadosPerfilIds` (control-mesa-reactividad-playoffs-plan.md, Fase 3
 * §2 — corrección del bug de "filtrado estricto de suplentes"): TODAS las
 * filas de `GET /convocados` (titulares + suplentes), no solo las
 * titulares. Antes de esta corrección, `suplentes` se calculaba como "todo
 * el plantel del CLUB que no es titular" — un jugador nunca convocado a
 * ESTE partido igual aparecía en "Entra". Ahora un jugador de `plantilla`
 * que no está en `convocadosPerfilIds` no entra a ninguno de los dos sets.
 *
 * Sin convocatoria guardada para este partido (`convocadosPerfilIds`
 * vacío): AMBOS sets vuelven vacíos, EXPLÍCITAMENTE — degradación con
 * gracia (D4, `partido.py:170-179`: "resultado directo" existe para
 * partidos sin alineación registrada). Cada call-site debe chequear
 * `titulares.size === 0 && suplentes.size === 0` y mostrar la plantilla
 * completa + un aviso, en vez de asumir que un set vacío "no filtra" por
 * accidente. */
export function deriveTitularSuplente(
  convocadosPerfilIds: Set<number>,
  titularesPerfilIds: Set<number>,
  plantilla: PlantillaJugador[],
): { titulares: Set<number>; suplentes: Set<number> } {
  if (convocadosPerfilIds.size === 0) {
    return { titulares: new Set(), suplentes: new Set() };
  }
  const titulares = new Set<number>();
  const suplentes = new Set<number>();
  for (const j of plantilla) {
    if (!convocadosPerfilIds.has(j.jugador_perfil_id)) continue; // no convocado a ESTE partido
    if (titularesPerfilIds.has(j.jugador_perfil_id)) titulares.add(j.jugador_id);
    else suplentes.add(j.jugador_id);
  }
  return { titulares, suplentes };
}

/** Quiénes están "en cancha" AHORA para elegir en un "Sale": titulares que
 * no salieron/fueron expulsados, MÁS suplentes que ya entraron (y no
 * volvieron a salir) — control-mesa-reactividad-playoffs-plan.md, Fase 3
 * §1 ("estado mutante en cambios"). Sin esto, un suplente que entra por un
 * Cambio queda inelegible para un Cambio posterior en el MISMO
 * batch/timeline (lesiones rápidas, etc.). Compone `salidosOExpulsados` y
 * `yaEntraron` (ya derivados por `deriveHistorialElegibilidad`) en vez de
 * reimplementar el historial — 1 sola fuente de verdad para ambos ejes de
 * la elegibilidad ("Sale" y "Entra"), mismo criterio de polaridad
 * explícita que `deriveTitularSuplente`. */
export function deriveEnCancha(
  titularesJugadorIds: Set<number>,
  salidosOExpulsados: Set<number>,
  yaEntraron: Set<number>,
): Set<number> {
  const enCancha = new Set(titularesJugadorIds);
  for (const id of yaEntraron) enCancha.add(id);
  for (const id of salidosOExpulsados) enCancha.delete(id);
  return enCancha;
}

/** exp.1 (docs/plans/cierre-pendientes-todos-plan.md) — estado de
 * tarjetas por jugador: "1A" (una amarilla), "2A" (dos, caso raro porque
 * la segunda ya autogenera una roja — igual se puede ver en la ventana
 * entre el insert de la 2ª amarilla y el refetch) o "R" (roja, propia o
 * automática por doble amarilla). Se deriva de `eventosRegistrados` YA
 * PERSISTIDOS en el servidor (`MesaPanel.tsx`, no del batch local sin
 * guardar de `ModalResultadoDirecto` — corrección de la revisión 3 del
 * plan: ese modal deriva estado local de un `otrosEventos` sin guardar,
 * un problema distinto). Roja siempre gana sobre amarilla: un jugador
 * expulsado no necesita ver "1A", ya no vuelve a jugar. */
export type EstadoTarjeta = "1A" | "2A" | "R";

export function deriveEstadoTarjetasPorJugador(
  eventosRegistrados: EventoRegistradoMinimo[],
  eventoNombrePorId: Map<number, string>,
): Map<number, EstadoTarjeta> {
  const amarillasPorJugador = new Map<number, number>();
  const rojaPorJugador = new Set<number>();
  for (const e of eventosRegistrados) {
    const nombreTipo = eventoNombrePorId.get(e.eventos_id);
    if (nombreTipo === "Tarjeta Amarilla") {
      amarillasPorJugador.set(e.jugador_id, (amarillasPorJugador.get(e.jugador_id) ?? 0) + 1);
    } else if (nombreTipo === "Tarjeta Roja") {
      rojaPorJugador.add(e.jugador_id);
    }
  }
  const estado = new Map<number, EstadoTarjeta>();
  for (const jugadorId of rojaPorJugador) {
    estado.set(jugadorId, "R");
  }
  for (const [jugadorId, cantidad] of amarillasPorJugador) {
    if (estado.has(jugadorId)) continue; // roja ya gana
    estado.set(jugadorId, cantidad >= 2 ? "2A" : "1A");
  }
  return estado;
}
