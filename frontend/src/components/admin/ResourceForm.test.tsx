import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { ResourceForm, type ResourceFormField } from "./ResourceForm";

describe("ResourceForm", () => {
  it("deshabilita el submit si falta un campo requerido", () => {
    const fields: ResourceFormField[] = [{ name: "nombre", label: "Nombre", type: "text", required: true }];
    render(<ResourceForm fields={fields} onSubmit={() => {}} submitting={false} submitError={null} />);
    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
  });

  it("habilita el submit y manda los valores cuando el campo requerido está completo", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const fields: ResourceFormField[] = [{ name: "nombre", label: "Nombre", type: "text", required: true }];
    render(<ResourceForm fields={fields} onSubmit={onSubmit} submitting={false} submitError={null} />);

    await user.type(screen.getByLabelText("Nombre"), "Copa Ecotec");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).toHaveBeenCalledWith({ nombre: "Copa Ecotec" });
  });

  it("campo number: convierte el valor a número antes de mandarlo", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const fields: ResourceFormField[] = [{ name: "dorsal", label: "Dorsal", type: "number" }];
    render(<ResourceForm fields={fields} onSubmit={onSubmit} submitting={false} submitError={null} />);

    await user.type(screen.getByLabelText("Dorsal"), "10");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).toHaveBeenCalledWith({ dorsal: 10 });
  });

  it("campo password: renderiza un input enmascarado (Fase 4, D3)", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn();
    const fields: ResourceFormField[] = [{ name: "password", label: "Contraseña", type: "password" }];
    render(<ResourceForm fields={fields} onSubmit={onSubmit} submitting={false} submitError={null} />);

    const input = screen.getByLabelText("Contraseña");
    expect(input).toHaveAttribute("type", "password");

    await user.type(input, "clave12345");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onSubmit).toHaveBeenCalledWith({ password: "clave12345" });
  });

  it("campo reference: muestra 'Cargando...' mientras optionsLoading", () => {
    const fields: ResourceFormField[] = [
      { name: "torneo_id", label: "Torneo", type: "reference", optionsLoading: true },
    ];
    render(<ResourceForm fields={fields} onSubmit={() => {}} submitting={false} submitError={null} />);
    expect(screen.getByRole("combobox", { name: "Torneo" })).toBeDisabled();
    expect(screen.getByText("Cargando...")).toBeInTheDocument();
  });

  it("campo reference: lista las opciones dadas", () => {
    const fields: ResourceFormField[] = [
      {
        name: "torneo_id",
        label: "Torneo",
        type: "reference",
        options: [
          { value: 1, label: "Copa Ecotec 2026" },
          { value: 2, label: "Liga Barrial" },
        ],
      },
    ];
    render(<ResourceForm fields={fields} onSubmit={() => {}} submitting={false} submitError={null} />);
    expect(screen.getByRole("option", { name: "Copa Ecotec 2026" })).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Liga Barrial" })).toBeInTheDocument();
  });

  it("muestra submitError cuando está presente", () => {
    render(
      <ResourceForm
        fields={[]}
        onSubmit={() => {}}
        submitting={false}
        submitError="fecha_fin no puede ser anterior a fecha_inicio."
      />,
    );
    expect(screen.getByText("fecha_fin no puede ser anterior a fecha_inicio.")).toBeInTheDocument();
  });

  it("submitting deshabilita el botón y cambia el texto", () => {
    render(<ResourceForm fields={[]} onSubmit={() => {}} submitting submitError={null} />);
    const boton = screen.getByRole("button", { name: "Guardando..." });
    expect(boton).toBeDisabled();
  });

  it("onCancel: renderiza el botón Cancelar y lo dispara al click", async () => {
    const user = userEvent.setup();
    const onCancel = vi.fn();
    render(<ResourceForm fields={[]} onSubmit={() => {}} submitting={false} submitError={null} onCancel={onCancel} />);
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onCancel).toHaveBeenCalled();
  });

  // torneos-admin-plan.md, Fase 2: campo Modalidad condicional a la
  // Disciplina elegida.
  describe("fields como función (campos condicionales)", () => {
    const camposCondicionales = (values: Record<string, string | number | null>): ResourceFormField[] => [
      {
        name: "disciplina",
        label: "Disciplina",
        type: "select",
        choices: ["Equipo", "Individual"],
      },
      ...(values.disciplina === "Individual"
        ? [{ name: "modalidad", label: "Modalidad", type: "select", choices: ["Individual", "Dobles"] } as ResourceFormField]
        : []),
    ];

    it("no muestra Modalidad por defecto (disciplina de tipo Equipo)", () => {
      render(<ResourceForm fields={camposCondicionales} onSubmit={() => {}} submitting={false} submitError={null} />);
      expect(screen.queryByLabelText("Modalidad")).not.toBeInTheDocument();
    });

    it("muestra Modalidad al elegir una disciplina Individual", async () => {
      const user = userEvent.setup();
      render(<ResourceForm fields={camposCondicionales} onSubmit={() => {}} submitting={false} submitError={null} />);
      await user.selectOptions(screen.getByLabelText("Disciplina"), "Individual");
      expect(screen.getByLabelText("Modalidad")).toBeInTheDocument();
    });

    it("EC-24: limpia Modalidad si se vuelve a una disciplina de tipo Equipo", async () => {
      const user = userEvent.setup();
      const onSubmit = vi.fn();
      render(<ResourceForm fields={camposCondicionales} onSubmit={onSubmit} submitting={false} submitError={null} />);

      await user.selectOptions(screen.getByLabelText("Disciplina"), "Individual");
      await user.selectOptions(screen.getByLabelText("Modalidad"), "Dobles");
      await user.selectOptions(screen.getByLabelText("Disciplina"), "Equipo");

      expect(screen.queryByLabelText("Modalidad")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Guardar" }));
      // No debe quedar un "modalidad": "Dobles" fantasma en el submit.
      expect(onSubmit).toHaveBeenCalledWith({ disciplina: "Equipo" });
    });
  });
});
