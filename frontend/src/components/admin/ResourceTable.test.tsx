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
    await user.click(screen.getByRole("button", { name: "Editar" }));
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
    expect(screen.getAllByRole("button", { name: "Dar de baja" })).toHaveLength(1);
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
    expect(screen.getAllByRole("button", { name: "Dar de baja" })).toHaveLength(1);
  });

  it("click en 'Dar de baja' llama a onSoftDelete con la fila", async () => {
    const user = userEvent.setup();
    const onSoftDelete = vi.fn();
    const rows: Fila[] = [{ id: 1, nombre: "Uno", estado: "Activo" }];
    render(
      <ResourceTable<Fila>
        rows={rows}
        columns={columnas}
        isLoading={false}
        isError={false}
        onSoftDelete={onSoftDelete}
      />,
    );
    await user.click(screen.getByRole("button", { name: "Dar de baja" }));
    expect(onSoftDelete).toHaveBeenCalledWith(rows[0]);
  });
});
