import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../test/msw-server";
import { createWrapper } from "../test/test-utils";
import { LIMITE_LISTA, useResourceCrud } from "./useResourceCrud";

const BASE = "http://127.0.0.1:8000/api/v1/test-resource";

interface TestOut {
  id: number;
  nombre: string;
  estado: string;
}

// Nota sobre el patrón mutate() + waitFor() en vez de await mutateAsync()
// dentro de act(): mutateAsync() resuelve la promesa antes de que React
// llegue a re-renderizar con el estado nuevo de la mutación — leer
// result.current inmediatamente después queda con el render VIEJO
// (status "idle", data undefined) de forma intermitente. waitFor() sondea
// hasta que el estado realmente se propaga — es el patrón que la propia
// documentación de TanStack Query recomienda para tests.

describe("useResourceCrud", () => {
  // El hook siempre dispara el GET de lista al montar (no es lazy) — los
  // tests que prueban create/update/softDelete/customAction necesitan que
  // ese GET no explote (onUnhandledRequest: "error" en setup.ts). Los
  // tests de "list:" lo overridean con su propio server.use().
  beforeEach(() => {
    server.use(http.get(BASE, () => HttpResponse.json([])));
  });

  it("list: trae los datos en éxito", async () => {
    server.use(http.get(BASE, () => HttpResponse.json([{ id: 1, nombre: "Uno", estado: "Activo" }])));

    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "list-ok", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.listQuery.isSuccess).toBe(true));
    expect(result.current.listQuery.data).toEqual([{ id: 1, nombre: "Uno", estado: "Activo" }]);
  });

  it("list: vacío no es un error", async () => {
    server.use(http.get(BASE, () => HttpResponse.json([])));

    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "list-empty", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.listQuery.isSuccess).toBe(true));
    expect(result.current.listQuery.data).toEqual([]);
  });

  // El techo de filas dejó de ser un fallo silencioso
  // (equipos-disciplina-navegacion-plan.md, Mejora #1): hasta que exista
  // paginación con cursor, lo mínimo es que la página PUEDA avisar que
  // está mostrando un recorte.
  it("list: marca truncado cuando la respuesta llega justo llena", async () => {
    const llena = Array.from({ length: LIMITE_LISTA }, (_, i) => ({
      id: i + 1,
      nombre: `Fila ${i + 1}`,
      estado: "Activo",
    }));
    server.use(http.get(BASE, () => HttpResponse.json(llena)));
    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "test-resource", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.listQuery.data).toHaveLength(LIMITE_LISTA));
    expect(result.current.truncado).toBe(true);
  });

  it("list: no marca truncado si entran todas las filas", async () => {
    server.use(http.get(BASE, () => HttpResponse.json([{ id: 1, nombre: "Uno", estado: "Activo" }])));
    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "test-resource", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.listQuery.data).toHaveLength(1));
    expect(result.current.truncado).toBe(false);
  });

  it("list: pide exactamente LIMITE_LISTA filas", async () => {
    let limitPedido: string | null = null;
    server.use(
      http.get(BASE, ({ request }) => {
        limitPedido = new URL(request.url).searchParams.get("limit");
        return HttpResponse.json([]);
      }),
    );
    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "test-resource", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.listQuery.isSuccess).toBe(true));
    // Si el `le=` del backend y esta constante se desincronizan, el
    // servidor devuelve 422 y este test es el que lo cuenta.
    expect(limitPedido).toBe(String(LIMITE_LISTA));
  });

  it("list: expone isError si el servidor falla", async () => {
    server.use(http.get(BASE, () => HttpResponse.json({ detail: "boom" }, { status: 500 })));

    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "list-error", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    await waitFor(() => expect(result.current.listQuery.isError).toBe(true));
  });

  it("create: éxito devuelve el recurso creado", async () => {
    server.use(
      http.post(BASE, async ({ request }) => {
        const body = (await request.json()) as { nombre: string };
        return HttpResponse.json({ id: 2, nombre: body.nombre, estado: "Activo" }, { status: 201 });
      }),
    );

    const { result } = renderHook(
      () =>
        useResourceCrud<TestOut, { nombre: string }>({
          resourceKey: "create-ok",
          basePath: "/api/v1/test-resource",
        }),
      { wrapper: createWrapper() },
    );

    result.current.create.mutate({ nombre: "Nuevo" });

    await waitFor(() => expect(result.current.create.isSuccess).toBe(true));
    expect(result.current.create.data).toEqual({ id: 2, nombre: "Nuevo", estado: "Activo" });
  });

  it.each([
    [422, { detail: [{ msg: "campo inválido" }] }],
    [400, { detail: "regla de negocio violada" }],
    [409, { detail: "ya existe un registro con esos datos" }],
  ])("create: %i queda accesible en mutation.error", async (status, body) => {
    server.use(http.post(BASE, () => HttpResponse.json(body, { status })));

    const { result } = renderHook(
      () =>
        useResourceCrud<TestOut, { nombre: string }>({
          resourceKey: `create-error-${status}`,
          basePath: "/api/v1/test-resource",
        }),
      { wrapper: createWrapper() },
    );

    result.current.create.mutate({ nombre: "x" });

    await waitFor(() => expect(result.current.create.isError).toBe(true));
    expect(result.current.create.error).toEqual(body);
  });

  it("update: hace PATCH al id correcto", async () => {
    server.use(
      http.patch(`${BASE}/5`, async ({ request }) => {
        const body = (await request.json()) as { nombre: string };
        return HttpResponse.json({ id: 5, nombre: body.nombre, estado: "Activo" });
      }),
    );

    const { result } = renderHook(
      () =>
        useResourceCrud<TestOut, unknown, { nombre: string }>({
          resourceKey: "update-ok",
          basePath: "/api/v1/test-resource",
        }),
      { wrapper: createWrapper() },
    );

    result.current.update.mutate({ id: 5, body: { nombre: "Editado" } });

    await waitFor(() => expect(result.current.update.isSuccess).toBe(true));
    expect(result.current.update.data).toEqual({ id: 5, nombre: "Editado", estado: "Activo" });
  });

  it("softDelete: hace DELETE al id correcto", async () => {
    server.use(http.delete(`${BASE}/7`, () => HttpResponse.json({ id: 7, nombre: "X", estado: "Inactivo" })));

    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "delete-ok", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    result.current.softDelete.mutate(7);

    await waitFor(() => expect(result.current.softDelete.isSuccess).toBe(true));
    expect(result.current.softDelete.data).toEqual({ id: 7, nombre: "X", estado: "Inactivo" });
  });

  it("customAction: llama al path y query dados (caso 'baja' de Plantillas)", async () => {
    server.use(
      http.post(`${BASE}/9/baja`, ({ request }) => {
        const url = new URL(request.url);
        expect(url.searchParams.get("fecha_fin")).toBe("2026-01-01");
        return HttpResponse.json({ id: 9, nombre: "Y", estado: "Inactivo" });
      }),
    );

    const { result } = renderHook(
      () => useResourceCrud<TestOut>({ resourceKey: "custom-action", basePath: "/api/v1/test-resource" }),
      { wrapper: createWrapper() },
    );

    result.current.customAction.mutate({
      path: "/api/v1/test-resource/9/baja",
      query: { fecha_fin: "2026-01-01" },
    });

    await waitFor(() => expect(result.current.customAction.isSuccess).toBe(true));
  });
});
