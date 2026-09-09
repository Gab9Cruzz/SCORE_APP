/** Lógica pura de la alineación, separada del gesto a propósito.
 *
 * El arrastre no se puede cubrir con tests (jsdom no implementa `PointerEvent`
 * ni `setPointerCapture`, y `getBoundingClientRect()` devuelve ceros), así que
 * todo lo que decide QUÉ pasa vive acá y se testea como función pura. El gesto
 * y el botón de tap son dos formas de invocar esto mismo.
 */

export type Zona = "titulares" | "suplentes";

export interface JugadorPlantilla {
  jugador_id: number;
  jugador: string;
  equipo_id: number;
  equipo: string;
  dorsal: number | null;
  jugador_perfil_id: number;
}

/** jugador_perfil_id -> titular. Ausente del Map = no convocado. */
export type Seleccion = Map<number, boolean>;

export function zonaDe(seleccion: Seleccion, perfilId: number): Zona | null {
  if (!seleccion.has(perfilId)) return null;
  return seleccion.get(perfilId) ? "titulares" : "suplentes";
}

/** Mueve un jugador a una zona. Devuelve un Map nuevo (no muta el original).
 *
 * Mover a la zona en la que ya está es un no-op que devuelve el MISMO objeto:
 * así un drop dentro de la propia zona no dispara re-render ni marca cambios
 * sin guardar. */
export function mover(seleccion: Seleccion, perfilId: number, zona: Zona): Seleccion {
  const actual = zonaDe(seleccion, perfilId);
  if (actual === zona) return seleccion;
  const copia = new Map(seleccion);
  copia.set(perfilId, zona === "titulares");
  return copia;
}

/** Convoca o desconvoca (el checkbox del Paso 1). Al convocar cae en suplentes,
 * como pide el requerimiento. */
export function alternarConvocado(seleccion: Seleccion, perfilId: number): Seleccion {
  const copia = new Map(seleccion);
  if (copia.has(perfilId)) copia.delete(perfilId);
  else copia.set(perfilId, false);
  return copia;
}

/** Marca como titulares a los primeros N por dorsal ascendente (los sin dorsal
 * al final). Atajo para el caso más común: el operador quiere el equipo tipo
 * sin ir de a uno. */
export function marcarPrimerosComoTitulares(
  seleccion: Seleccion,
  plantilla: JugadorPlantilla[],
  cantidad: number,
): Seleccion {
  const convocados = plantilla
    .filter((j) => seleccion.has(j.jugador_perfil_id))
    .sort((a, b) => {
      if (a.dorsal == null && b.dorsal == null) return a.jugador.localeCompare(b.jugador);
      if (a.dorsal == null) return 1;
      if (b.dorsal == null) return -1;
      return a.dorsal - b.dorsal;
    });
  const copia = new Map(seleccion);
  convocados.forEach((j, i) => copia.set(j.jugador_perfil_id, i < cantidad));
  return copia;
}

export function contarTitulares(seleccion: Seleccion, plantilla: JugadorPlantilla[]): number {
  return plantilla.filter((j) => seleccion.get(j.jugador_perfil_id) === true).length;
}

/** Área 1 (modo-vivo-sustituciones-cierre-plan.md, T2): ¿hay lugar para un
 * titular más en ESTE equipo? Reversión explícita de la Decisión Audit
 * #12 del plan anterior (diferida dos veces, reabierta con evidencia
 * concreta: Fútbol 7 aceptaba 8 titulares sin ningún aviso). Bloqueo
 * client-side ANTES del POST — el backend igual valida
 * (ConvocadoAPartidoService + trigger fn_validar_tope_titulares), nunca se
 * confía solo en esto. */
export function hayLugarParaTitular(seleccion: Seleccion, plantilla: JugadorPlantilla[], maximo: number): boolean {
  return contarTitulares(seleccion, plantilla) < maximo;
}

export function contarConvocados(seleccion: Seleccion, plantilla: JugadorPlantilla[]): number {
  return plantilla.filter((j) => seleccion.has(j.jugador_perfil_id)).length;
}

/** Orden estable dentro de una zona: dorsal ascendente, sin dorsal al final,
 * desempate alfabético. Con 18 jugadores el orden importa para encontrarlos. */
export function ordenarPlantilla(jugadores: JugadorPlantilla[]): JugadorPlantilla[] {
  return [...jugadores].sort((a, b) => {
    if (a.dorsal == null && b.dorsal == null) return a.jugador.localeCompare(b.jugador);
    if (a.dorsal == null) return 1;
    if (b.dorsal == null) return -1;
    return a.dorsal - b.dorsal;
  });
}

export function hayCambios(guardada: Seleccion, actual: Seleccion): boolean {
  if (guardada.size !== actual.size) return true;
  for (const [perfilId, titular] of actual) {
    if (!guardada.has(perfilId) || guardada.get(perfilId) !== titular) return true;
  }
  return false;
}

/** Convierte una lista guardada del backend al Map que usa la UI. */
export function seleccionDesdeConvocados(
  convocados: { jugador_perfil_id: number; titular: boolean }[],
): Seleccion {
  return new Map(convocados.map((c) => [c.jugador_perfil_id, c.titular]));
}

/** Default invertido: sin convocatoria guardada, toda la plantilla arranca
 * convocada y el operador destilda a los ausentes.
 *
 * En un plantel de 14-18 donde faltan 2-3, destildar ausentes son 2 toques
 * contra los 14 que costaba tildar presentes uno por uno. */
export function seleccionInicial(
  guardados: { jugador_perfil_id: number; titular: boolean }[],
  plantilla: JugadorPlantilla[],
): Seleccion {
  if (guardados.length > 0) return seleccionDesdeConvocados(guardados);
  return new Map(plantilla.map((j) => [j.jugador_perfil_id, false]));
}
