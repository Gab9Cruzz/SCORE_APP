import { beforeEach, describe, expect, it } from "vitest";
import {
  guardarEventoPendiente,
  leerEventoPendiente,
  limpiarEventoPendiente,
} from "./colaOfflineEventos";

describe("colaOfflineEventos", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("no hay nada pendiente por default", () => {
    expect(leerEventoPendiente(3)).toBeNull();
  });

  it("guarda y lee el mismo evento, con guardadoEn agregado", () => {
    guardarEventoPendiente(3, { partidos_id: 3, jugador_id: 5, equipo_id: 1, eventos_id: 1, minuto: 30 });

    const leido = leerEventoPendiente(3);
    expect(leido).not.toBeNull();
    expect(leido).toMatchObject({ partidos_id: 3, jugador_id: 5, equipo_id: 1, eventos_id: 1, minuto: 30 });
    expect(typeof leido?.guardadoEn).toBe("string");
  });

  it("está aislado por partidoId — no mezcla la cola de dos partidos", () => {
    guardarEventoPendiente(3, { partidos_id: 3, jugador_id: 5, equipo_id: 1, eventos_id: 1, minuto: 30 });
    guardarEventoPendiente(4, { partidos_id: 4, jugador_id: 9, equipo_id: 2, eventos_id: 2, minuto: 10 });

    expect(leerEventoPendiente(3)?.jugador_id).toBe(5);
    expect(leerEventoPendiente(4)?.jugador_id).toBe(9);
  });

  it("limpiar saca solo el partido pedido", () => {
    guardarEventoPendiente(3, { partidos_id: 3, jugador_id: 5, equipo_id: 1, eventos_id: 1, minuto: 30 });
    guardarEventoPendiente(4, { partidos_id: 4, jugador_id: 9, equipo_id: 2, eventos_id: 2, minuto: 10 });

    limpiarEventoPendiente(3);

    expect(leerEventoPendiente(3)).toBeNull();
    expect(leerEventoPendiente(4)).not.toBeNull();
  });

  it("un JSON corrupto en localStorage se trata como 'nada pendiente', no rompe", () => {
    localStorage.setItem("score-app.mesa-offline.3", "{esto no es json válido");
    expect(leerEventoPendiente(3)).toBeNull();
  });
});
