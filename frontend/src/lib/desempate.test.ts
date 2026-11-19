import { describe, expect, it } from "vitest";
import {
  badgePenales,
  consecuenciaCortaDesempate,
  etiquetaReglaDesempate,
  formatearResultadoDesempate,
  fraseResultadoDesempate,
  type ResultadoDesempate,
} from "./desempate";

// TASK-047: lib/desempate.ts no tenía pruebas propias (33 % de líneas). Es
// la fuente única de los textos de desempate de tres pantallas, así que se
// prueba la matriz Metodo_Desempate × Hubo_Tiempo_Extra entera.

function r(parcial: Partial<ResultadoDesempate>): ResultadoDesempate {
  return {
    golesLocal: 2,
    golesVisitante: 2,
    metodoDesempate: null,
    huboTiempoExtra: false,
    penalesLocal: null,
    penalesVisitante: null,
    ...parcial,
  };
}

describe("formatearResultadoDesempate", () => {
  it.each([
    ["sin desempate", r({ golesLocal: 3, golesVisitante: 1 }), "3 - 1"],
    ["tiempo extra", r({ metodoDesempate: "Tiempo_Extra", huboTiempoExtra: true, golesLocal: 3 }), "3 - 2 a.e.t."],
    ["penales en tiempo regular", r({ metodoDesempate: "Penales", penalesLocal: 4, penalesVisitante: 2 }), "2 - 2 (4-2 pen.)"],
    [
      "penales tras tiempo extra",
      r({ metodoDesempate: "Penales", huboTiempoExtra: true, penalesLocal: 5, penalesVisitante: 4 }),
      "2 - 2 a.e.t. (5-4 pen.)",
    ],
    ["decisión manual", r({ metodoDesempate: "Manual" }), "2 - 2 (def.)"],
    ["decisión manual tras tiempo extra", r({ metodoDesempate: "Manual", huboTiempoExtra: true }), "2 - 2 a.e.t. (def.)"],
    // Celda imposible (penales sin marcador de tanda): cae al formato base.
    ["penales sin tanda", r({ metodoDesempate: "Penales" }), "2 - 2"],
  ])("%s", (_, resultado, esperado) => {
    expect(formatearResultadoDesempate(resultado)).toBe(esperado);
  });
});

describe("fraseResultadoDesempate", () => {
  it("sin desempate no hay nada que contar", () => {
    expect(fraseResultadoDesempate(r({ golesLocal: 1, golesVisitante: 0 }))).toBeNull();
  });

  it.each([
    [r({ metodoDesempate: "Penales", penalesLocal: 4, penalesVisitante: 2 }), "Definido en penales 4-2 tras 2-2 en el tiempo regular."],
    [
      r({ metodoDesempate: "Penales", huboTiempoExtra: true, penalesLocal: 4, penalesVisitante: 3 }),
      "Definido en penales 4-3 tras 2-2 en el tiempo extra.",
    ],
    [r({ metodoDesempate: "Tiempo_Extra", huboTiempoExtra: true, golesLocal: 3 }), "Definido en el tiempo extra 3-2."],
    [r({ metodoDesempate: "Manual" }), "Empate en tiempo regular, resuelto por decisión."],
    [r({ metodoDesempate: "Manual", huboTiempoExtra: true }), "Empate tras el tiempo extra, resuelto por decisión."],
  ])("%#: %s", (resultado, esperado) => {
    expect(fraseResultadoDesempate(resultado)).toBe(esperado);
  });

  it("penales sin marcador de tanda no inventa una frase", () => {
    expect(fraseResultadoDesempate(r({ metodoDesempate: "Penales" }))).toBeNull();
  });
});

describe("badgePenales", () => {
  it("solo la tanda, cuando la hubo", () => {
    expect(badgePenales(r({ metodoDesempate: "Penales", penalesLocal: 4, penalesVisitante: 3 }))).toBe("pen. 4-3");
  });

  it.each([r({}), r({ metodoDesempate: "Manual" }), r({ metodoDesempate: "Penales", penalesLocal: 4 })])(
    "sin tanda completa no hay badge (%#)",
    (resultado) => {
      expect(badgePenales(resultado)).toBeNull();
    },
  );
});

describe("reglas de desempate", () => {
  it.each([
    ["Manual", "Empate → lo decidís vos", "lo decidís vos"],
    ["Penales_Directo", "Empate → penales", "penales"],
    ["Tiempo_Extra_Penales", "Empate → tiempo extra", "tiempo extra"],
    ["Penales_Salvo_Final", "Empate → penales (tiempo extra en la Final)", "penales (tiempo extra en la Final)"],
  ] as const)("%s", (metodo, chip, corta) => {
    expect(etiquetaReglaDesempate(metodo)).toBe(chip);
    expect(consecuenciaCortaDesempate(metodo)).toBe(corta);
  });

  it("sin regla conocida no se muestra nada", () => {
    for (const metodo of [null, undefined]) {
      expect(etiquetaReglaDesempate(metodo)).toBeNull();
      expect(consecuenciaCortaDesempate(metodo)).toBeNull();
    }
  });
});
