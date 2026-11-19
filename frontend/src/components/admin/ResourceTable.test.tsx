import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ResourceTable } from "./ResourceTable";

interface Fila {
  id: number;
  nombre: string;
  estado: string;
}

const columnas = [{ key: "nombre", label: "Nombre" }];

describe("ResourceTable", () => {
  it("muestra 'Cargando...' mientras isLoading", () => {
    render(<ResourceTable<Fila> rows={[]} columns={columnas} isLoading isError={false} />);
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
  });

  it("muestra el error si isError", () => {
    render(<ResourceTable<Fila> rows={[]} columns={columnas} isLoading={false} isError />);
    expect(screen.getByText("No se pudo cargar la lista.")).toBeInTheDocument();
  });

  it("muestra el mensaje de vacío configurable", () => {
    render(
      <ResourceTable<Fila>
        rows={[]}
        columns={columnas}
        isLoading={false}
        isError={false}
        emptyMessage="Nada por acá."
      />,
    );
    expect(screen.getByText("Nada por acá.")).toBeInTheDocument();
  });

  it("renderiza las filas con las columnas dadas", () => {
    const rows: Fila[] = [
      { id: 1, nombre: "Uno", estado: "Activo" },
      { id: 2, nombre: "Dos", estado: "Activo" },
    ];
    render(<ResourceTable<Fila> rows={rows} columns={columnas} isLoading={false} isError={false} />);
    expect(screen.getByText("Uno")).toBeInTheDocument();
    expect(screen.getByText("Dos")).toBeInTheDocument();
  });

  it("click en 'Editar' llama a onSelect con la fila", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    const rows: Fila[] = [{ id: 1, nombre: "Uno", estado: "Activo" }];
    render(
      <ResourceTable<Fila> rows={rows} columns={columnas} isLoading={false} isError={false} onSelect={onSelect} />,
    );
    await user.click(screen.getByRole("button", { name: /^Editar/ }));
    expect(onSelect).toHaveBeenCalledWith(rows[0]);
  });

  it("oculta el botón de baja para filas ya dadas de baja", () => {
    const rows: Fila[] = [
      { id: 1, nombre: "Activa", estado: "Activo" },
      { id: 2, nombre: "Inactiva", estado: "Inactivo" },
    ];
    render(
      <ResourceTable<Fila>
        rows={rows}
        columns={columnas}
        isLoading={false}
        isError={false}
        onSoftDelete={() => {}}
      />,
    );
    expect(screen.getAllByRole("button", { name: /^Dar de baja/ })).toHaveLength(1);
  });

  it("isSelf oculta el botón de baja solo para la fila que matchea (Fase 4, D2a)", () => {
    const rows: Fila[] = [
      { id: 1, nombre: "Yo", estado: "Activo" },
      { id: 2, nombre: "Otro", estado: "Activo" },
    ];
    render(
      <ResourceTable<Fila>
        rows={rows}
        columns={columnas}
        isLoading={false}
        isError={false}
        onSoftDelete={() => {}}
        isSelf={(row) => row.id === 1}
      />,
    );
    expect(screen.getAllByRole("button", { name: /^Dar de baja/ })).toHaveLength(1);
  });

  // TASK-038 (UX-06): la baja pide confirmación en la misma fila.
  function renderConBaja(extra: Partial<Parameters<typeof ResourceTable<Fila>>[0]> = {}) {
    const onSoftDelete = vi.fn();
    const rows: Fila[] = [
      { id: 1, nombre: "Halcones FC", estado: "Activo" },
      { id: 2, nombre: "Tiburones FC", estado: "Activo" },
    ];
    render(
      <ResourceTable<Fila>
        rows={rows}
        columns={columnas}
        isLoading={false}
        isError={false}
        onSoftDelete={onSoftDelete}
        {...extra}
      />,
    );
    return { onSoftDelete, rows };
  }

  it("un clic en 'Dar de baja' no ejecuta la baja: pide confirmación", async () => {
    const user = userEvent.setup();
    const { onSoftDelete, rows } = renderConBaja();

    await user.click(screen.getAllByRole("button", { name: /^Dar de baja/ })[0]);
    expect(onSoftDelete).not.toHaveBeenCalled();

    await user.click(screen.getByRole("button", { name: "Confirmar" }));
    expect(onSoftDelete).toHaveBeenCalledWith(rows[0]);
  });

  it("la confirmación nombra el elemento afectado, o usa el texto de la pantalla", async () => {
    const user = userEvent.setup();
    renderConBaja();
    await user.click(screen.getAllByRole("button", { name: /^Dar de baja/ })[0]);
    expect(screen.getByRole("alert")).toHaveTextContent("¿Dar de baja «Halcones FC»?");
  });

  it("acepta un texto propio con la consecuencia", async () => {
    const user = userEvent.setup();
    renderConBaja({ confirmacion: (r) => `Se cancela ${r.nombre}; sus jugadores quedan libres.` });
    await user.click(screen.getAllByRole("button", { name: /^Dar de baja/ })[1]);
    expect(screen.getByRole("alert")).toHaveTextContent("Se cancela Tiburones FC; sus jugadores quedan libres.");
  });

  it("funciona solo con teclado: el foco va a 'Volver' y Escape cierra devolviendo el foco", async () => {
    const user = userEvent.setup();
    const { onSoftDelete } = renderConBaja();
    const boton = screen.getAllByRole("button", { name: /^Dar de baja/ })[0];

    boton.focus();
    await user.keyboard("{Enter}");
    expect(screen.getByRole("button", { name: "Volver" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: /^Dar de baja/ })[0]).toHaveFocus();
    expect(onSoftDelete).not.toHaveBeenCalled();

    // Y confirmar también se puede con teclado.
    await user.keyboard("{Enter}");
    await user.keyboard("{Shift>}{Tab}{/Shift}");
    expect(screen.getByRole("button", { name: "Confirmar" })).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(onSoftDelete).toHaveBeenCalledTimes(1);
  });

  // TASK-037 (UX-04): diez "Editar" iguales no le dicen nada a un lector de
  // pantalla; el nombre accesible lleva la fila.
  it("los botones de cada fila se anuncian con el nombre de la fila", () => {
    renderConBaja({ onSelect: vi.fn() });
    expect(screen.getByRole("button", { name: "Editar Halcones FC" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dar de baja Tiburones FC" })).toBeInTheDocument();
  });

  it("nombreFila reemplaza el nombre por defecto", () => {
    renderConBaja({ onSelect: vi.fn(), nombreFila: (r) => `equipo ${r.id}` });
    expect(screen.getByRole("button", { name: "Editar equipo 2" })).toBeInTheDocument();
  });

  it("la tabla tiene caption y encabezados de columna con scope", () => {
    renderConBaja({ etiqueta: "Equipos inscritos" });
    expect(screen.getByRole("table", { name: "Equipos inscritos" })).toBeInTheDocument();
    for (const th of screen.getAllByRole("columnheader")) expect(th).toHaveAttribute("scope", "col");
  });

  it("'Volver' cierra sin ejecutar", async () => {
    const user = userEvent.setup();
    const { onSoftDelete } = renderConBaja();
    await user.click(screen.getAllByRole("button", { name: /^Dar de baja/ })[0]);
    await user.click(screen.getByRole("button", { name: "Volver" }));
    expect(onSoftDelete).not.toHaveBeenCalled();
    expect(screen.getAllByRole("button", { name: /^Dar de baja/ })).toHaveLength(2);
  });
});
