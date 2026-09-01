import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import type { components } from "../../api/schema";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { AuditoriaAdminPage } from "./AuditoriaAdmin";

const AUDITORIA = "http://127.0.0.1:8000/api/v1/auditoria";

type Auditoria = components["schemas"]["AuditoriaOut"];

const ALTA_TORNEO: Auditoria = {
  id: 1,
  usuario_id: 7,
  tabla: "torneo",
  registro_id: 42,
  accion: "crear",
  datos_anteriores: null,
  datos_nuevos: { nombre: "Copa Ecotec 2026" },
  ip: "203.0.113.7",
  user_agent: "curl/8.0",
  fecha: "2026-08-27T21:00:00",
};
const MODIFICACION_EQUIPO: Auditoria = {
  id: 2,
  usuario_id: 7,
  tabla: "equipos",
  registro_id: 5,
  accion: "modificar",
  datos_anteriores: { nombre: "Nombre Viejo" },
  datos_nuevos: { nombre: "Nombre Nuevo" },
  ip: "203.0.113.7",
  user_agent: "curl/8.0",
  fecha: "2026-08-27T21:05:00",
};
const BAJA_JUGADOR: Auditoria = {
  id: 3,
  usuario_id: null,
  tabla: "jugadores",
  registro_id: 9,
  accion: "eliminar",
  datos_anteriores: { estado: "Activo" },
  datos_nuevos: { estado: "Inactivo" },
  ip: null,
  user_agent: null,
  fecha: "2026-08-27T21:10:00",
};

/** El backend filtra; el handler tiene que respetar los query params o el
 * test estaría verificando un filtro que en producción no existe. */
function handlerAuditoria(filas: Auditoria[]) {
  return http.get(AUDITORIA, ({ request }) => {
    const q = new URL(request.url).searchParams;
    const tabla = q.get("tabla");
    const accion = q.get("accion");
    const registroId = q.get("registro_id");
    return HttpResponse.json(
      filas.filter(
        (f) =>
          (tabla === null || f.tabla === tabla) &&
          (accion === null || f.accion === accion) &&
          (registroId === null || f.registro_id === Number(registroId)),
      ),
    );
  });
}

function montar(filas: Auditoria[]) {
  server.use(handlerAuditoria(filas));
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <AuditoriaAdminPage />
    </Wrapper>,
  );
}

describe("AuditoriaAdminPage", () => {
  it("lista alta, modificación y baja con su entidad y acción", async () => {
    montar([ALTA_TORNEO, MODIFICACION_EQUIPO, BAJA_JUGADOR]);

    // "Alta"/"Modificación"/"Baja" también son las labels del <select> de
    // filtro, así que hay que buscar el badge dentro de la fila, no el
    // texto suelto (que matchea dos elementos: la opción y el badge).
    const filaTorneo = (await screen.findByText("torneo #42")).closest("tr");
    expect(filaTorneo).not.toBeNull();
    expect(within(filaTorneo as HTMLElement).getByText("Alta")).toBeInTheDocument();

    const filaEquipo = screen.getByText("equipos #5").closest("tr");
    expect(within(filaEquipo as HTMLElement).getByText("Modificación")).toBeInTheDocument();

    const filaJugador = screen.getByText("jugadores #9").closest("tr");
    expect(within(filaJugador as HTMLElement).getByText("Baja")).toBeInTheDocument();
  });

  it("resume el diff antes → después de una modificación", async () => {
    montar([MODIFICACION_EQUIPO]);

    expect(await screen.findByText("nombre: Nombre Viejo → Nombre Nuevo")).toBeInTheDocument();
  });

  it("un cambio sin actor resuelto se muestra sin usuario, no como error", async () => {
    montar([BAJA_JUGADOR]);

    await screen.findByText("jugadores #9");
    // BAJA_JUGADOR tiene usuario_id: null — la columna "Hecho por" lo dice
    // en vez de romper.
    const filas = screen.getAllByText("—");
    expect(filas.length).toBeGreaterThan(0);
  });

  it("filtra por acción contra el servidor", async () => {
    montar([ALTA_TORNEO, MODIFICACION_EQUIPO]);
    const user = userEvent.setup();

    await screen.findByText("torneo #42");
    await user.selectOptions(screen.getByLabelText("Acción"), "modificar");

    await waitFor(() => expect(screen.queryByText("torneo #42")).not.toBeInTheDocument());
    expect(screen.getByText("equipos #5")).toBeInTheDocument();
  });

  it("filtra por tabla (autocomplete de nombres reales) contra el servidor", async () => {
    montar([ALTA_TORNEO, MODIFICACION_EQUIPO]);
    const user = userEvent.setup();

    await screen.findByText("torneo #42");
    // 3A-1: ya no es un <input> de texto libre, es un <select> con las
    // __tablename__ reales — value=label, "equipos" matchea tal cual.
    await user.selectOptions(screen.getByLabelText("Tabla"), "equipos");

    await waitFor(() => expect(screen.queryByText("torneo #42")).not.toBeInTheDocument());
    expect(screen.getByText("equipos #5")).toBeInTheDocument();
  });

  it("filtra por registro_id contra el servidor (3A-2)", async () => {
    montar([ALTA_TORNEO, MODIFICACION_EQUIPO]);
    const user = userEvent.setup();

    await screen.findByText("torneo #42");
    await user.type(screen.getByLabelText("ID de registro"), "5");

    await waitFor(() => expect(screen.queryByText("torneo #42")).not.toBeInTheDocument());
    expect(screen.getByText("equipos #5")).toBeInTheDocument();
  });

  it("no ofrece editar ni dar de baja: la bitácora es solo lectura", async () => {
    montar([ALTA_TORNEO]);

    await screen.findByText("torneo #42");
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dar de baja" })).not.toBeInTheDocument();
  });

  it("el vacío filtrado no dice lo mismo que el vacío real", async () => {
    montar([]);
    const user = userEvent.setup();

    expect(await screen.findByText("Todavía no hay cambios registrados.")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Tabla"), "torneo");
    expect(await screen.findByText(/Ningún cambio coincide con estos filtros/)).toBeInTheDocument();
  });

  it("el botón de exportar CSV está deshabilitado sin filas cargadas", async () => {
    montar([]);

    await screen.findByText("Todavía no hay cambios registrados.");
    expect(screen.getByRole("button", { name: /Descargar CSV/ })).toBeDisabled();
  });

  it("exporta un CSV con las filas visibles al hacer clic (3A-3)", async () => {
    montar([ALTA_TORNEO, MODIFICACION_EQUIPO]);
    const user = userEvent.setup();
    await screen.findByText("torneo #42");

    const boton = screen.getByRole("button", { name: /Descargar CSV/ });
    expect(boton).not.toBeDisabled();

    // jsdom no implementa la descarga real — createObjectURL/click no
    // deben tirar, que es lo único que este entorno puede verificar sin
    // un navegador real.
    const creado = vi.fn(() => "blob:mock");
    const revocado = vi.fn();
    URL.createObjectURL = creado;
    URL.revokeObjectURL = revocado;

    await user.click(boton);

    expect(creado).toHaveBeenCalledTimes(1);
    expect(revocado).toHaveBeenCalledTimes(1);
  });
});
