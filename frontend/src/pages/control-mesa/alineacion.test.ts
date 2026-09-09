import { describe, expect, it } from "vitest";
import {
  type JugadorPlantilla,
  type Seleccion,
  alternarConvocado,
  contarTitulares,
  hayCambios,
  marcarPrimerosComoTitulares,
  mover,
  ordenarPlantilla,
  seleccionInicial,
  zonaDe,
} from "./alineacion";

/** El GESTO de arrastre no se testea acá, y no es un olvido: jsdom no
 * implementa `PointerEvent` ni `setPointerCapture`, y `getBoundingClientRect()`
 * devuelve todo en cero, así que no hay forma de decidir sobre qué zona se
 * soltó. Por eso toda la lógica que decide QUÉ pasa vive en funciones puras y
 * se cubre acá; el gesto queda para QA manual en navegador real.
 *
 * Es también la razón por la que el botón de tap es de primera clase y no un
 * repliegue: es el camino que sí se puede verificar automáticamente. */

const PLANTILLA: JugadorPlantilla[] = [
  { jugador_id: 1, jugador: "Vera, Andrés", equipo_id: 1, equipo: "Tiburones", dorsal: 9, jugador_perfil_id: 50 },
  { jugador_id: 2, jugador: "Gómez, Luis", equipo_id: 1, equipo: "Tiburones", dorsal: 4, jugador_perfil_id: 51 },
  { jugador_id: 3, jugador: "Díaz, Ana", equipo_id: 1, equipo: "Tiburones", dorsal: null, jugador_perfil_id: 52 },
  { jugador_id: 4, jugador: "Pérez, Juan", equipo_id: 1, equipo: "Tiburones", dorsal: 7, jugador_perfil_id: 53 },
];

function seleccionDe(entradas: [number, boolean][]): Seleccion {
  return new Map(entradas);
}

describe("mover", () => {
  it("sube un suplente a titulares", () => {
    const s = seleccionDe([[50, false]]);
    expect(zonaDe(mover(s, 50, "titulares"), 50)).toBe("titulares");
  });

  it("baja un titular a suplentes", () => {
    const s = seleccionDe([[50, true]]);
    expect(zonaDe(mover(s, 50, "suplentes"), 50)).toBe("suplentes");
  });

  it("mover a la zona en la que ya está es un no-op que devuelve el MISMO objeto", () => {
    // Es lo que hace que soltar dentro de la propia zona no marque cambios sin
    // guardar ni dispare un re-render.
    const s = seleccionDe([[50, true]]);
    expect(mover(s, 50, "titulares")).toBe(s);
  });

  it("no muta la selección original", () => {
    const s = seleccionDe([[50, false]]);
    mover(s, 50, "titulares");
    expect(s.get(50)).toBe(false);
  });
});

describe("alternarConvocado", () => {
  it("al convocar, el jugador cae en suplentes (no en titulares)", () => {
    const s = alternarConvocado(new Map(), 50);
    expect(zonaDe(s, 50)).toBe("suplentes");
  });

  it("al desconvocar, sale del Map (no queda como false)", () => {
    const s = alternarConvocado(seleccionDe([[50, true]]), 50);
    expect(s.has(50)).toBe(false);
    expect(zonaDe(s, 50)).toBeNull();
  });
});

describe("seleccionInicial — default invertido", () => {
  it("sin convocatoria guardada, TODA la plantilla arranca convocada", () => {
    // En un plantel de 14-18 donde faltan 2-3, destildar ausentes son 2 toques
    // contra los 14 que costaba tildar presentes uno por uno.
    const s = seleccionInicial([], PLANTILLA);
    expect(s.size).toBe(PLANTILLA.length);
    expect([...s.values()].every((titular) => titular === false)).toBe(true);
  });

  it("con convocatoria guardada, respeta lo guardado y no invierte nada", () => {
    const s = seleccionInicial([{ jugador_perfil_id: 50, titular: true }], PLANTILLA);
    expect(s.size).toBe(1);
    expect(s.get(50)).toBe(true);
  });
});

describe("marcarPrimerosComoTitulares", () => {
  it("marca los primeros N por dorsal ascendente", () => {
    const convocados = seleccionInicial([], PLANTILLA);
    const s = marcarPrimerosComoTitulares(convocados, PLANTILLA, 2);
    // Dorsales: 4 (Gómez), 7 (Pérez), 9 (Vera), null (Díaz)
    expect(s.get(51)).toBe(true);
    expect(s.get(53)).toBe(true);
    expect(s.get(50)).toBe(false);
    expect(s.get(52)).toBe(false);
  });

  it("los jugadores sin dorsal quedan al final", () => {
    const convocados = seleccionInicial([], PLANTILLA);
    const s = marcarPrimerosComoTitulares(convocados, PLANTILLA, 3);
    expect(s.get(52)).toBe(false); // Díaz, sin dorsal
  });

  it("solo considera a los convocados, no a toda la plantilla", () => {
    const soloDos = seleccionDe([
      [50, false],
      [52, false],
    ]);
    const s = marcarPrimerosComoTitulares(soloDos, PLANTILLA, 5);
    expect(s.has(51)).toBe(false);
    expect(contarTitulares(s, PLANTILLA)).toBe(2);
  });
});

describe("ordenarPlantilla", () => {
  it("ordena por dorsal ascendente con los sin dorsal al final", () => {
    expect(ordenarPlantilla(PLANTILLA).map((j) => j.dorsal)).toEqual([4, 7, 9, null]);
  });
});

describe("hayCambios", () => {
  it("detecta un jugador agregado", () => {
    expect(hayCambios(seleccionDe([[50, false]]), seleccionDe([[50, false], [51, false]]))).toBe(true);
  });

  it("detecta un cambio de titular que NO cambia la cantidad de convocados", () => {
    // El caso que rompía la concurrencia optimista por IDs: el set de jugadores
    // es idéntico, lo único que cambió es el flag.
    expect(hayCambios(seleccionDe([[50, false]]), seleccionDe([[50, true]]))).toBe(true);
  });

  it("no marca cambios cuando la selección es equivalente", () => {
    expect(hayCambios(seleccionDe([[50, true], [51, false]]), seleccionDe([[51, false], [50, true]]))).toBe(false);
  });
});
