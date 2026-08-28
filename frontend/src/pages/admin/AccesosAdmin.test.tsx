import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import type { components } from "../../api/schema";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { AccesosAdminPage } from "./AccesosAdmin";

const ACCESOS = "http://127.0.0.1:8000/api/v1/accesos";

// Tipado desde el contrato GENERADO del backend, no de la inferencia de los
// fixtures: si el día de mañana AccesoOut gana o pierde un campo, este
// archivo deja de compilar en vez de seguir mockeando una forma que la API
// ya no devuelve.
type Acceso = components["schemas"]["AccesoOut"];

const UA_CHROME =
  "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36";

const FALLIDO_CUENTA_REAL: Acceso = {
  id: 3,
  usuario_id: 7,
  username: "admin1",
  exitoso: false,
  motivo: "credenciales",
  ip: "203.0.113.7",
  user_agent: UA_CHROME,
  fecha: "2026-08-27T21:30:00",
};
const FALLIDO_USUARIO_INEXISTENTE: Acceso = {
  id: 2,
  usuario_id: null,
  username: "root",
  exitoso: false,
  motivo: "credenciales",
  ip: "198.51.100.4",
  user_agent: "curl/8.0",
  fecha: "2026-08-27T21:20:00",
};
const EXITOSO: Acceso = {
  id: 1,
  usuario_id: 7,
  username: "admin1",
  exitoso: true,
  motivo: null,
  ip: "203.0.113.7",
  user_agent: UA_CHROME,
  fecha: "2026-08-27T21:00:00",
};

/** El backend filtra; el handler tiene que respetar los query params o el
 * test estaría verificando un filtro que en producción no existe. */
function handlerAccesos(filas: Acceso[]) {
  return http.get(ACCESOS, ({ request }) => {
    const q = new URL(request.url).searchParams;
    const exitoso = q.get("exitoso");
    const username = q.get("username");
    return HttpResponse.json(
      filas.filter(
        (f) =>
          (exitoso === null || f.exitoso === (exitoso === "true")) &&
          (username === null || f.username.toLowerCase().includes(username.toLowerCase())),
      ),
    );
  });
}

function montar(filas: Acceso[]) {
  server.use(handlerAccesos(filas));
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <AccesosAdminPage />
    </Wrapper>,
  );
}

describe("AccesosAdminPage", () => {
  it("arranca mostrando solo los intentos fallidos", async () => {
    montar([FALLIDO_CUENTA_REAL, FALLIDO_USUARIO_INEXISTENTE, EXITOSO]);

    // Entrar acá es casi siempre por sospecha: el default es lo sospechoso.
    expect(await screen.findAllByText("Usuario o contraseña incorrectos")).toHaveLength(2);
    expect(screen.queryByText("Entró")).not.toBeInTheDocument();
  });

  it("distingue un intento contra una cuenta real de uno contra un usuario inexistente", async () => {
    montar([FALLIDO_CUENTA_REAL, FALLIDO_USUARIO_INEXISTENTE]);

    await screen.findByText("root");
    // Es la diferencia entre "alguien le apunta a una cuenta que existe" y
    // "alguien tira nombres al azar".
    expect(screen.getByText("no existe")).toBeInTheDocument();
    expect(screen.getByText("#7")).toBeInTheDocument();
  });

  it("muestra la IP y resume el user-agent, con el original en el title", async () => {
    montar([FALLIDO_CUENTA_REAL]);

    await screen.findByText("203.0.113.7");
    const resumen = screen.getByText("Chrome · Windows");
    expect(resumen).toHaveAttribute("title", UA_CHROME);
  });

  it("permite pasar a los exitosos y volver a todos", async () => {
    montar([FALLIDO_CUENTA_REAL, EXITOSO]);
    const user = userEvent.setup();

    await screen.findByText("Usuario o contraseña incorrectos");

    await user.selectOptions(screen.getByLabelText("Resultado"), "true");
    expect(await screen.findByText("Entró")).toBeInTheDocument();
    expect(screen.queryByText("Usuario o contraseña incorrectos")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Limpiar filtros" }));
    await waitFor(() => expect(screen.getByText("Entró")).toBeInTheDocument());
    expect(screen.getByText("Usuario o contraseña incorrectos")).toBeInTheDocument();
  });

  it("busca por usuario contra el servidor", async () => {
    montar([FALLIDO_CUENTA_REAL, FALLIDO_USUARIO_INEXISTENTE]);
    const user = userEvent.setup();

    await screen.findByText("root");
    await user.type(screen.getByLabelText("Buscar usuario"), "root");

    await waitFor(() => expect(screen.queryByText("admin1")).not.toBeInTheDocument());
    expect(screen.getByText("root")).toBeInTheDocument();
  });

  it("no ofrece editar ni dar de baja: la bitácora es solo lectura", async () => {
    montar([FALLIDO_CUENTA_REAL]);

    await screen.findByText("admin1");
    // Ni siquiera para AdminGeneral — una bitácora editable no prueba nada.
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dar de baja" })).not.toBeInTheDocument();
  });

  it("el vacío filtrado no dice lo mismo que el vacío real", async () => {
    montar([]);
    const user = userEvent.setup();

    // Arranca con el filtro "solo fallidos" puesto.
    expect(await screen.findByText(/Ningún acceso coincide con estos filtros/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Limpiar filtros" }));
    expect(await screen.findByText("Todavía no hay accesos registrados.")).toBeInTheDocument();
  });
});
