import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ErrorBoundary } from "./ErrorBoundary";

let debeFallar = true;
function Fragil() {
  if (debeFallar) throw new Error("boom de prueba");
  return <p>Contenido sano</p>;
}

describe("ErrorBoundary (TASK-041)", () => {
  // React y el propio límite escriben el error en la consola; es lo
  // esperado y no debe ensuciar la salida de la suite.
  let consola: ReturnType<typeof vi.spyOn>;
  beforeEach(() => {
    debeFallar = true;
    consola = vi.spyOn(console, "error").mockImplementation(() => {});
  });
  afterEach(() => consola.mockRestore());

  it("muestra el aviso de recuperación en lugar de dejar la pantalla en blanco", () => {
    render(
      <>
        <nav>Barra</nav>
        <ErrorBoundary>
          <Fragil />
        </ErrorBoundary>
      </>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 1, name: /Algo falló al mostrar esta página/ })).toBeInTheDocument();
    expect(screen.getByText(/boom de prueba/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recargar" })).toBeInTheDocument();
    // Lo que está fuera del límite sigue ahí.
    expect(screen.getByText("Barra")).toBeInTheDocument();
  });

  it("registra el error", () => {
    render(
      <ErrorBoundary ambito="el panel de mesa">
        <Fragil />
      </ErrorBoundary>,
    );
    expect(consola).toHaveBeenCalledWith(
      "[ErrorBoundary]",
      "el panel de mesa",
      expect.objectContaining({ message: "boom de prueba" }),
      expect.anything(),
    );
  });

  it("Reintentar vuelve a dibujar el contenido", async () => {
    render(
      <ErrorBoundary>
        <Fragil />
      </ErrorBoundary>,
    );
    debeFallar = false;
    await userEvent.setup().click(screen.getByRole("button", { name: "Reintentar" }));
    expect(screen.getByText("Contenido sano")).toBeInTheDocument();
  });

  it("al cambiar la clave (otra ruta) se olvida el error", () => {
    const { rerender } = render(
      <ErrorBoundary claveReinicio="/a">
        <Fragil />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("alert")).toBeInTheDocument();
    debeFallar = false;
    rerender(
      <ErrorBoundary claveReinicio="/b">
        <Fragil />
      </ErrorBoundary>,
    );
    expect(screen.getByText("Contenido sano")).toBeInTheDocument();
  });

  it("anidado usa h2 para no competir con el h1 de la página", () => {
    render(
      <ErrorBoundary ambito="el panel de mesa" anidado>
        <Fragil />
      </ErrorBoundary>,
    );
    expect(screen.getByRole("heading", { level: 2, name: /el panel de mesa/ })).toBeInTheDocument();
  });
});
