import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState, type ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";
import { Modal } from "./Modal";

// TASK-034 / TASK-035 (UX-03): el modal único.

function ConDisparador(props: {
  onCerrar?: () => void;
  sinGuardar?: boolean;
  cierreBloqueado?: boolean;
  contenido?: (pedirCierre: () => void) => ReactNode;
}) {
  const [abierto, setAbierto] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setAbierto(true)}>
        Abrir
      </button>
      {abierto && (
        <Modal
          titulo="Gestionar torneos"
          sinGuardar={props.sinGuardar}
          cierreBloqueado={props.cierreBloqueado}
          onCerrar={() => {
            props.onCerrar?.();
            setAbierto(false);
          }}
        >
          {(pedirCierre) =>
            props.contenido?.(pedirCierre) ?? (
              <>
                <input aria-label="Buscar" />
                <button type="button" onClick={pedirCierre}>
                  Cancelar
                </button>
              </>
            )
          }
        </Modal>
      )}
    </>
  );
}

async function abrir(ui: ReturnType<typeof userEvent.setup>) {
  await ui.click(screen.getByRole("button", { name: "Abrir" }));
}

describe("Modal", () => {
  it("tiene nombre, el foco entra y Tab no sale del panel", async () => {
    const user = userEvent.setup();
    render(<ConDisparador />);
    await abrir(user);

    expect(screen.getByRole("dialog", { name: "Gestionar torneos" })).toHaveAttribute("aria-modal", "true");
    expect(screen.getByLabelText("Buscar")).toHaveFocus();

    await user.tab();
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
    await user.tab();
    expect(screen.getByLabelText("Buscar")).toHaveFocus();
    await user.tab({ shift: true });
    expect(screen.getByRole("button", { name: "Cancelar" })).toHaveFocus();
  });

  it("Escape cierra y el foco vuelve al botón que lo abrió", async () => {
    const user = userEvent.setup();
    const onCerrar = vi.fn();
    render(<ConDisparador onCerrar={onCerrar} />);
    await abrir(user);

    await user.keyboard("{Escape}");
    expect(onCerrar).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Abrir" })).toHaveFocus();
  });

  it("un clic en el fondo cierra; uno dentro del panel no", async () => {
    const user = userEvent.setup();
    render(<ConDisparador />);
    await abrir(user);

    await user.click(screen.getByLabelText("Buscar"));
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    const fondo = screen.getByRole("dialog").parentElement!;
    await user.click(fondo);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("una selección que empieza en el panel y termina en el fondo no cierra", () => {
    render(<Modal titulo="T" onCerrar={vi.fn()}>{null}</Modal>);
    const panel = screen.getByRole("dialog");
    const fondo = panel.parentElement!;
    fireEvent.mouseDown(panel);
    fireEvent.click(fondo);
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("con datos sin guardar, Escape pregunta en vez de cerrar", async () => {
    const user = userEvent.setup();
    const onCerrar = vi.fn();
    render(<ConDisparador onCerrar={onCerrar} sinGuardar />);
    await abrir(user);

    await user.keyboard("{Escape}");
    expect(onCerrar).not.toHaveBeenCalled();
    expect(screen.getByRole("alert")).toHaveTextContent("Hay datos sin guardar");
    expect(screen.getByRole("button", { name: "Seguir editando" })).toHaveFocus();

    // Un segundo Escape vuelve a la edición, no cierra.
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
    expect(screen.getByRole("dialog")).toBeInTheDocument();

    // "Cancelar" (pedirCierre) y el fondo pasan por la misma pregunta.
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(screen.getByRole("alert")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Descartar y cerrar" }));
    expect(onCerrar).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("con una operación en curso no se cierra", async () => {
    const user = userEvent.setup();
    const onCerrar = vi.fn();
    render(<ConDisparador onCerrar={onCerrar} cierreBloqueado />);
    await abrir(user);
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Cancelar" }));
    expect(onCerrar).not.toHaveBeenCalled();
  });

  it("con un modal dentro de otro, Escape cierra solo el de adelante", async () => {
    const user = userEvent.setup();
    const cerrarAfuera = vi.fn();
    function Anidados() {
      const [interno, setInterno] = useState(true);
      return (
        <Modal titulo="Afuera" onCerrar={cerrarAfuera}>
          <button type="button">Algo</button>
          {interno && (
            <Modal titulo="Adentro" onCerrar={() => setInterno(false)}>
              <button type="button">Elegir</button>
            </Modal>
          )}
        </Modal>
      );
    }
    render(<Anidados />);
    expect(screen.getByRole("button", { name: "Elegir" })).toHaveFocus();

    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Adentro" })).not.toBeInTheDocument();
    expect(cerrarAfuera).not.toHaveBeenCalled();

    await user.keyboard("{Escape}");
    expect(cerrarAfuera).toHaveBeenCalledTimes(1);
  });

  it("bloquea el desplazamiento de la página mientras está abierto", async () => {
    const user = userEvent.setup();
    render(<ConDisparador />);
    expect(document.body.style.overflow).toBe("");
    await abrir(user);
    expect(document.body.style.overflow).toBe("hidden");
    await user.keyboard("{Escape}");
    expect(document.body.style.overflow).toBe("");
  });

  it("un redibujo del padre no le roba el foco al usuario", async () => {
    const user = userEvent.setup();
    function Padre() {
      const [n, setN] = useState(0);
      return (
        <Modal titulo="Contador" onCerrar={() => {}}>
          <input aria-label="Primero" />
          <button type="button" onClick={() => setN(n + 1)}>
            Sumar {n}
          </button>
        </Modal>
      );
    }
    render(<Padre />);
    await user.click(screen.getByRole("button", { name: "Sumar 0" }));
    expect(screen.getByRole("button", { name: "Sumar 1" })).toHaveFocus();
  });
});
