import { describe, expect, it } from "vitest";
import { apiErrorMessage } from "./client";

// TASK-015: traducción de los códigos de error que el backend devuelve tal
// cual (RAISE EXCEPTION de triggers) y del 500 genérico con identificador.
describe("apiErrorMessage", () => {
  it.each([
    "jugador_ya_activo_en_este_torneo",
    "equipo_ya_asignado_a_otro_grupo_en_esta_fase",
    "hito_ya_registrado",
    "partido_corrido_sin_ganador",
  ])("traduce el código %s", (codigo) => {
    const mensaje = apiErrorMessage({ detail: codigo });
    expect(mensaje).not.toBe(codigo);
    expect(mensaje).not.toMatch(/_/);
  });

  it("en un error interno muestra el identificador para reportarlo", () => {
    const mensaje = apiErrorMessage({ detail: "Error interno.", id: "3f2a1b7c-0000-4000-8000-000000000000" });
    expect(mensaje).toContain("3f2a1b7c-0000-4000-8000-000000000000");
  });

  it("los mensajes en texto llano pasan tal cual", () => {
    expect(apiErrorMessage({ detail: "Este torneo no está cerrado." })).toBe("Este torneo no está cerrado.");
  });
});
