import { describe, expect, it } from "vitest";
import { contarSlots, descartarSlotYReconciliar, reconciliarSlots, resolverTipoYEquipoDeSlot, type SlotGol } from "./reconciliarSlots";

let contador = 0;
function crearId(): string {
  contador += 1;
  return `slot-${contador}`;
}

describe("reconciliarSlots", () => {
  it("subir el marcador agrega slots vacíos al final, sin tocar los existentes", () => {
    const existente: SlotGol[] = [{ id: "a", lado: "local", jugadorId: 10, minuto: "23" }];
    const { slots, pendienteConfirmar } = reconciliarSlots(existente, "local", 3, crearId);
    expect(pendienteConfirmar).toBeNull();
    expect(contarSlots(slots, "local")).toBe(3);
    // El slot ya lleno no se tocó.
    expect(slots.find((s) => s.id === "a")).toEqual(existente[0]);
    // Los 2 nuevos están vacíos.
    const nuevos = slots.filter((s) => s.id !== "a");
    expect(nuevos.every((s) => s.jugadorId === null && s.minuto === "")).toBe(true);
  });

  it("bajar el marcador sin afectar slots llenos quita solo los vacíos", () => {
    const existente: SlotGol[] = [
      { id: "a", lado: "local", jugadorId: 10, minuto: "23" },
      { id: "b", lado: "local", jugadorId: null, minuto: "" },
    ];
    const { slots, pendienteConfirmar } = reconciliarSlots(existente, "local", 1, crearId);
    expect(pendienteConfirmar).toBeNull();
    expect(slots).toEqual([existente[0]]);
  });

  it("bajar el marcador afectando un slot lleno requiere confirmación — no descarta nada solo", () => {
    const existente: SlotGol[] = [
      { id: "a", lado: "local", jugadorId: 10, minuto: "23" },
      { id: "b", lado: "local", jugadorId: 14, minuto: "55" },
    ];
    const resultado = reconciliarSlots(existente, "local", 1, crearId);
    expect(resultado.pendienteConfirmar).not.toBeNull();
    expect(resultado.pendienteConfirmar?.candidatos).toHaveLength(2);
    // Nada se tocó todavía.
    expect(resultado.slots).toEqual(existente);
  });

  it("no toca slots del otro lado", () => {
    const existente: SlotGol[] = [
      { id: "a", lado: "local", jugadorId: 10, minuto: "23" },
      { id: "b", lado: "visitante", jugadorId: 7, minuto: "40" },
    ];
    const { slots } = reconciliarSlots(existente, "local", 2, crearId);
    expect(slots.find((s) => s.id === "b")).toEqual(existente[1]);
  });

  it("marcador sin cambios es un no-op", () => {
    const existente: SlotGol[] = [{ id: "a", lado: "local", jugadorId: 10, minuto: "23" }];
    const { slots, pendienteConfirmar } = reconciliarSlots(existente, "local", 1, crearId);
    expect(slots).toBe(existente);
    expect(pendienteConfirmar).toBeNull();
  });
});

describe("descartarSlotYReconciliar", () => {
  it("descarta el slot elegido y aplica el marcador nuevo", () => {
    const existente: SlotGol[] = [
      { id: "a", lado: "local", jugadorId: 10, minuto: "23" },
      { id: "b", lado: "local", jugadorId: 14, minuto: "55" },
    ];
    const { slots, pendienteConfirmar } = descartarSlotYReconciliar(existente, "b", "local", 1, crearId);
    expect(pendienteConfirmar).toBeNull();
    expect(slots).toEqual([existente[0]]);
  });
});

describe("resolverTipoYEquipoDeSlot", () => {
  const equipoIdDelJugador = (id: number) => ({ 10: 1, 14: 1, 7: 2, 9: 2 })[id as 10 | 14 | 7 | 9];

  it("slot vacío no resuelve nada", () => {
    expect(resolverTipoYEquipoDeSlot({ id: "a", lado: "local", jugadorId: null, minuto: "" }, 1, 2, equipoIdDelJugador)).toBeNull();
  });

  it("jugador del mismo equipo que el lado del slot => Gol", () => {
    const r = resolverTipoYEquipoDeSlot({ id: "a", lado: "local", jugadorId: 10, minuto: "23" }, 1, 2, equipoIdDelJugador);
    expect(r).toEqual({ tipo: "Gol", equipoId: 1 });
  });

  it("jugador del equipo RIVAL del lado del slot => Autogol, acreditado al equipo del jugador (el que concede)", () => {
    const r = resolverTipoYEquipoDeSlot({ id: "a", lado: "local", jugadorId: 7, minuto: "10" }, 1, 2, equipoIdDelJugador);
    expect(r).toEqual({ tipo: "Autogol", equipoId: 2 });
  });

  it("simétrico para el lado visitante", () => {
    const r = resolverTipoYEquipoDeSlot({ id: "a", lado: "visitante", jugadorId: 10, minuto: "10" }, 1, 2, equipoIdDelJugador);
    expect(r).toEqual({ tipo: "Autogol", equipoId: 1 });
  });
});
