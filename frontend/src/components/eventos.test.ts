import { describe, expect, it } from "vitest";
import { deriveEnCancha, deriveHistorialElegibilidad, deriveTitularSuplente, type PlantillaJugador } from "./eventos";

const EVENTO_NOMBRE_POR_ID = new Map<number, string>([
  [1, "Gol"],
  [2, "Autogol"],
  [3, "Tarjeta Amarilla"],
  [4, "Tarjeta Roja"],
  [5, "Cambio"],
]);

function plantillaDe(jugadorId: number, jugadorPerfilId: number, equipoId = 1): PlantillaJugador {
  return { jugador_id: jugadorId, jugador: `J${jugadorId}`, equipo_id: equipoId, equipo: "Equipo", dorsal: null, jugador_perfil_id: jugadorPerfilId };
}

describe("deriveHistorialElegibilidad", () => {
  it("sin eventos, ambos sets vacíos", () => {
    const { salidosOExpulsados, yaEntraron } = deriveHistorialElegibilidad([], EVENTO_NOMBRE_POR_ID);
    expect(salidosOExpulsados.size).toBe(0);
    expect(yaEntraron.size).toBe(0);
  });

  it("un Cambio marca a quien sale como salido y a quien entra como ya-entrado", () => {
    const { salidosOExpulsados, yaEntraron } = deriveHistorialElegibilidad(
      [{ jugador_id: 5, jugador_id_entra: 6, eventos_id: 5 }],
      EVENTO_NOMBRE_POR_ID,
    );
    expect(salidosOExpulsados.has(5)).toBe(true);
    expect(yaEntraron.has(6)).toBe(true);
  });

  it("una Tarjeta Roja marca como salido, sin marcar a nadie como ya-entrado", () => {
    const { salidosOExpulsados, yaEntraron } = deriveHistorialElegibilidad(
      [{ jugador_id: 7, jugador_id_entra: null, eventos_id: 4 }],
      EVENTO_NOMBRE_POR_ID,
    );
    expect(salidosOExpulsados.has(7)).toBe(true);
    expect(yaEntraron.size).toBe(0);
  });

  it("un Gol no marca a nadie como salido", () => {
    const { salidosOExpulsados } = deriveHistorialElegibilidad(
      [{ jugador_id: 9, jugador_id_entra: null, eventos_id: 1 }],
      EVENTO_NOMBRE_POR_ID,
    );
    expect(salidosOExpulsados.size).toBe(0);
  });
});

describe("deriveTitularSuplente", () => {
  const plantilla = [plantillaDe(101, 1), plantillaDe(102, 2), plantillaDe(103, 3)];

  it("sin convocatoria guardada (convocadosPerfilIds vacío), ambos sets vuelven vacíos explícitamente", () => {
    const { titulares, suplentes } = deriveTitularSuplente(new Set(), new Set(), plantilla);
    expect(titulares.size).toBe(0);
    expect(suplentes.size).toBe(0);
  });

  it("con convocatoria, separa titulares de suplentes por jugador_id (no jugador_perfil_id)", () => {
    const { titulares, suplentes } = deriveTitularSuplente(new Set([1, 2, 3]), new Set([1, 2]), plantilla);
    expect(titulares.has(101)).toBe(true);
    expect(titulares.has(102)).toBe(true);
    expect(titulares.has(103)).toBe(false);
    expect(suplentes.has(103)).toBe(true);
    expect(suplentes.has(101)).toBe(false);
  });

  it("titulares y suplentes son disjuntos y cubren toda la plantilla CONVOCADA", () => {
    const { titulares, suplentes } = deriveTitularSuplente(new Set([1, 2, 3]), new Set([2]), plantilla);
    expect(titulares.size + suplentes.size).toBe(plantilla.length);
    for (const id of titulares) expect(suplentes.has(id)).toBe(false);
  });

  it("regresión — un jugador del club NUNCA convocado a este partido no aparece en ningún set (control-mesa-reactividad-playoffs-plan.md, Fase 3 §2)", () => {
    // Perfil 3 (jugador 103) está en la plantilla del club pero NO en
    // convocadosPerfilIds — antes de la corrección, deriveTitularSuplente
    // lo trataba igual como "suplente" con solo mirar la plantilla
    // completa contra los titulares.
    const { titulares, suplentes } = deriveTitularSuplente(new Set([1, 2]), new Set([1]), plantilla);
    expect(titulares.has(101)).toBe(true);
    expect(suplentes.has(102)).toBe(true);
    expect(titulares.has(103)).toBe(false);
    expect(suplentes.has(103)).toBe(false); // ni titular ni suplente — nunca convocado
  });
});

describe("deriveEnCancha", () => {
  it("sin cambios registrados, en cancha = exactamente los titulares", () => {
    const enCancha = deriveEnCancha(new Set([101, 102]), new Set(), new Set());
    expect(enCancha).toEqual(new Set([101, 102]));
  });

  it("un titular que salió por Cambio ya no está en cancha", () => {
    const enCancha = deriveEnCancha(new Set([101, 102]), new Set([101]), new Set());
    expect(enCancha.has(101)).toBe(false);
    expect(enCancha.has(102)).toBe(true);
  });

  it("un suplente que ya entró por Cambio SÍ está en cancha — estado mutante (Fase 3 §1)", () => {
    const enCancha = deriveEnCancha(new Set([101, 102]), new Set([101]), new Set([201]));
    expect(enCancha.has(201)).toBe(true);
    expect(enCancha.size).toBe(2); // 102 (titular que no salió) + 201 (suplente que entró)
  });

  it("un suplente que entró y luego volvió a salir (2do Cambio) ya no está en cancha", () => {
    // 201 entró por A (queda en yaEntraron) y después salió en un 2do
    // Cambio (queda también en salidosOExpulsados) — la resta gana.
    const enCancha = deriveEnCancha(new Set([101]), new Set([101, 201]), new Set([201]));
    expect(enCancha.has(201)).toBe(false);
    expect(enCancha.has(101)).toBe(false);
  });
});
