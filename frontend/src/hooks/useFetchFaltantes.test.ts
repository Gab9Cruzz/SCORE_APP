import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../test/msw-server";
import { createWrapper } from "../test/test-utils";
import { useNombrePorIdConFaltantes, useNombresPorIds } from "./useFetchFaltantes";

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";

describe("useFetchFaltantes (TASK-039)", () => {
  it("pide todos los que faltan en UNA petición con ?ids=, ordenados y sin repetir", async () => {
    const pedidos: URLSearchParams[] = [];
    server.use(
      http.get(EQUIPOS, ({ request }) => {
        const params = new URL(request.url).searchParams;
        pedidos.push(params);
        const ids = params.get("ids")!.split(",").map(Number);
        return HttpResponse.json(ids.map((id) => ({ id, nombre: `Equipo ${id}` })));
      }),
    );
    const base = new Map([[1, "Ya conocido"]]);
    const { result } = renderHook(() => useNombrePorIdConFaltantes("/api/v1/equipos", base, [9, 1, 3, 9, null]), {
      wrapper: createWrapper(),
    });

    await waitFor(() => expect(result.current.get(9)).toBe("Equipo 9"));
    expect(result.current.get(3)).toBe("Equipo 3");
    expect(result.current.get(1)).toBe("Ya conocido");
    expect(pedidos).toHaveLength(1);
    expect(pedidos[0].get("ids")).toBe("3,9");
    expect(pedidos[0].get("limit")).toBe("2");
  });

  it("sin nada que resolver no pide nada", async () => {
    let pedidos = 0;
    server.use(
      http.get(EQUIPOS, () => {
        pedidos++;
        return HttpResponse.json([]);
      }),
    );
    const { result } = renderHook(() => useNombresPorIds("/api/v1/equipos", [null, undefined]), {
      wrapper: createWrapper(),
    });
    expect(result.current.size).toBe(0);
    await new Promise((r) => setTimeout(r, 20));
    expect(pedidos).toBe(0);
  });

  it("más de 200 ids se reparten en tandas de 200", async () => {
    const tandas: number[] = [];
    server.use(
      http.get(EQUIPOS, ({ request }) => {
        const ids = new URL(request.url).searchParams.get("ids")!.split(",").map(Number);
        tandas.push(ids.length);
        return HttpResponse.json(ids.map((id) => ({ id, nombre: `E${id}` })));
      }),
    );
    const ids = Array.from({ length: 250 }, (_, i) => i + 1);
    const { result } = renderHook(() => useNombresPorIds("/api/v1/equipos", ids), { wrapper: createWrapper() });

    await waitFor(() => expect(result.current.size).toBe(250));
    expect(tandas.sort((a, b) => a - b)).toEqual([50, 200]);
  });
});
