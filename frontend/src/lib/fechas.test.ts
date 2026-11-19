import { afterEach, describe, expect, it, vi } from "vitest";
import { LOCALE, formatearFecha, hoyISO, parsearFecha, sumarDias } from "./fechas";

// TASK-028 (FE-06): fechas sin toISOString() y sin interpretar una fecha
// sola ("YYYY-MM-DD") como medianoche UTC, que en Ecuador (UTC−5) se ve
// como el día anterior.
describe("fechas", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("una fecha sola se toma como ese día local, no como medianoche UTC", () => {
    const d = parsearFecha("2026-03-01");
    expect([d.getFullYear(), d.getMonth(), d.getDate()]).toEqual([2026, 2, 1]);
  });

  it("una fecha con hora sin zona se toma como hora local (la del negocio)", () => {
    const d = parsearFecha("2026-03-01T16:30:00");
    expect([d.getDate(), d.getHours(), d.getMinutes()]).toEqual([1, 16, 30]);
  });

  it("formatear una fecha sola muestra ese mismo día", () => {
    expect(formatearFecha("2026-03-01")).toContain("1");
    expect(formatearFecha("2026-03-01")).not.toContain("28");
  });

  it.each([
    ["2026-03-01", 1, "2026-03-02"],
    ["2026-03-01", -1, "2026-02-28"],
    ["2026-12-31", 1, "2027-01-01"],
    ["2028-02-28", 1, "2028-02-29"],
    ["2026-11-01", 30, "2026-12-01"],
    ["2026-01-01", -365, "2025-01-01"],
  ])("sumarDias(%s, %i) = %s", (base, dias, esperado) => {
    expect(sumarDias(base, dias)).toBe(esperado);
  });

  // TASK-040 (FUN-17): el resultado no depende de la zona del navegador.
  // Node aplica un cambio de process.env.TZ en caliente.
  it.each(["Pacific/Kiritimati", "Asia/Kolkata", "UTC", "America/Guayaquil", "Pacific/Pago_Pago"])(
    "sumarDias da lo mismo con el navegador en %s",
    (zona) => {
      const original = process.env.TZ;
      process.env.TZ = zona;
      try {
        expect(sumarDias("2026-05-10", 1)).toBe("2026-05-11");
        expect(sumarDias("2026-03-08", -1)).toBe("2026-03-07");
        expect(sumarDias("2026-11-01", 1)).toBe("2026-11-02");
      } finally {
        process.env.TZ = original;
      }
    },
  );

  it("hoyISO es el día de la zona del negocio, no el de UTC", () => {
    // 2026-11-19 03:00 UTC = 2026-11-18 22:00 en Guayaquil (UTC−5).
    vi.useFakeTimers();
    vi.setSystemTime(new Date(Date.UTC(2026, 10, 19, 3, 0, 0)));
    expect(hoyISO()).toBe("2026-11-18");
  });

  it("hoyISO por la mañana coincide con UTC", () => {
    vi.useFakeTimers();
    vi.setSystemTime(new Date(Date.UTC(2026, 10, 19, 15, 0, 0)));
    expect(hoyISO()).toBe("2026-11-19");
  });

  it("usa la configuración regional del negocio", () => {
    expect(LOCALE).toBe("es-EC");
  });
});
