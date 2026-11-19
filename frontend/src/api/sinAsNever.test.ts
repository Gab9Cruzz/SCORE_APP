import { describe, expect, it } from "vitest";

// TASK-032 (FE-03): el cliente tipado no se apaga con `as never`. El único
// lugar donde se le quita el tipo es api/rutaDinamica.ts (con `as unknown as`,
// documentado). Una página que no logra tipar un cuerpo tiene que usar el
// esquema `*Create`/`*Update` de schema.d.ts, no silenciar al compilador.
const fuentes = import.meta.glob(["/src/**/*.{ts,tsx}", "!/src/**/*.test.{ts,tsx}"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

describe("cliente tipado", () => {
  it("lee los fuentes", () => {
    expect(Object.keys(fuentes).length).toBeGreaterThan(50);
  });

  it("ningún archivo usa `as never`", () => {
    const conCast = Object.entries(fuentes)
      .filter(([, codigo]) => /\bas never\b/.test(codigo.replace(/\/\*[\s\S]*?\*\/|\/\/.*$/gm, "")))
      .map(([archivo]) => archivo);
    expect(conCast).toEqual([]);
  });
});
