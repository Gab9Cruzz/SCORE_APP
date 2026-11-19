import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { Button } from "./Button";
import { Field } from "./Field";
import { Table } from "./Table";

// TASK-034: una prueba (o un grupo) por componente base. Modal tiene las
// suyas en Modal.test.tsx (TASK-035).

describe("Button", () => {
  it("es type=button por defecto: no envía el formulario que lo contiene", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn((e: SubmitEvent) => e.preventDefault());
    render(
      <form onSubmit={(e) => onSubmit(e.nativeEvent as SubmitEvent)}>
        <Button>Editar</Button>
        <Button variante="primario" type="submit">
          Guardar
        </Button>
      </form>,
    );
    await user.click(screen.getByRole("button", { name: "Editar" }));
    expect(onSubmit).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Guardar" }));
    expect(onSubmit).toHaveBeenCalledTimes(1);
  });

  it("aplica la clase de la variante; enlace conserva link-button", () => {
    render(
      <>
        <Button>Secundario</Button>
        <Button variante="primario">Primario</Button>
        <Button variante="peligro">Peligro</Button>
        <Button variante="enlace" className="extra">
          Enlace
        </Button>
      </>,
    );
    expect(screen.getByRole("button", { name: "Secundario" })).toHaveClass("boton", "boton--secundario");
    expect(screen.getByRole("button", { name: "Primario" })).toHaveClass("boton--primario");
    expect(screen.getByRole("button", { name: "Peligro" })).toHaveClass("boton--peligro");
    expect(screen.getByRole("button", { name: "Enlace" })).toHaveClass("boton--enlace", "link-button", "extra");
  });
});

describe("Field", () => {
  it("asocia la etiqueta al control y enlaza ayuda y error", () => {
    render(
      <Field etiqueta="Correo" ayuda="Se usa para recuperar la cuenta." error="Formato inválido.">
        {(p) => <input {...p} />}
      </Field>,
    );
    const control = screen.getByLabelText("Correo");
    expect(control).toHaveClass("campo__control");
    expect(control).toHaveAttribute("aria-invalid", "true");
    expect(control).toHaveAccessibleDescription("Se usa para recuperar la cuenta. Formato inválido.");
  });

  it("sin error no marca el control como inválido ni lo describe", () => {
    render(<Field etiqueta="Nombre">{(p) => <input {...p} />}</Field>);
    const control = screen.getByLabelText("Nombre");
    expect(control).not.toHaveAttribute("aria-invalid");
    expect(control).not.toHaveAttribute("aria-describedby");
  });
});

describe("Table", () => {
  it("muestra carga, error y vacío con los textos comunes", () => {
    const { rerender } = render(
      <Table encabezados={["A"]} cargando>
        {null}
      </Table>,
    );
    expect(screen.getByText("Cargando...")).toBeInTheDocument();

    rerender(
      <Table encabezados={["A"]} error>
        {null}
      </Table>,
    );
    expect(screen.getByText("No se pudo cargar la lista.")).toBeInTheDocument();

    rerender(
      <Table encabezados={["A"]} vacio mensajeVacio="Sin equipos.">
        {null}
      </Table>,
    );
    expect(screen.getByText("Sin equipos.")).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("renderiza encabezados y filas; la columna sin título se llama Acciones", () => {
    render(
      <Table encabezados={["Equipo", null]} etiqueta="Inscriptos">
        <tr>
          <td>Halcones</td>
          <td>
            <button type="button">Editar</button>
          </td>
        </tr>
      </Table>,
    );
    expect(screen.getByRole("table", { name: "Inscriptos" })).toBeInTheDocument();
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(["Equipo", "Acciones"]);
    expect(screen.getByRole("cell", { name: "Halcones" })).toBeInTheDocument();
  });
});
