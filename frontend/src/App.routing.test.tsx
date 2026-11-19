import { QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";
import { App } from "./App";
import { TOKEN_STORAGE_KEY } from "./api/client";
import { AuthProvider } from "./auth/AuthContext";
import { server } from "./test/msw-server";
import { createTestQueryClient } from "./test/test-utils";

// Mismo key privado que AuthContext.tsx (ver UsuariosAdmin.test.tsx).
const SESSION_STORAGE_KEY = "score-app.session";

function sembrarSesion(rol: string, id: number) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username: "usuario_test", rol, id }));
}

const LOGIN = "http://127.0.0.1:8000/api/v1/auth/login";
const ME = "http://127.0.0.1:8000/api/v1/auth/me";
const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";
const PARTIDOS = "http://127.0.0.1:8000/api/v1/partidos";
const USUARIOS = "http://127.0.0.1:8000/api/v1/usuarios";

function renderApp(initialPath: string) {
  const queryClient = createTestQueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[initialPath]}>
        <AuthProvider>
          <App />
        </AuthProvider>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

/** La barra pública de disciplinas pide esto en cualquier ruta. */
function disciplinasDisponibles() {
  server.use(http.get("http://127.0.0.1:8000/api/v1/disciplinas/con-partidos", () => HttpResponse.json([])));
}

function mockLogin(rol: string) {
  server.use(
    http.post(LOGIN, () => HttpResponse.json({ access_token: "fake-token", token_type: "bearer", rol })),
  );
}

async function iniciarSesion() {
  const user = userEvent.setup();
  await user.type(screen.getByLabelText("Usuario"), "usuario_test");
  await user.type(screen.getByLabelText("Contraseña"), "clave12345");
  await user.click(screen.getByRole("button", { name: "Ingresar" }));
}

describe("Ruteo y redirect por rol (roles-3-modulos-plan.md, Fase 2, D2)", () => {
  beforeEach(() => {
    server.use(
      http.get(TORNEOS, () => HttpResponse.json([])),
      http.get(PARTIDOS, () => HttpResponse.json([])),
      http.get(USUARIOS, () => HttpResponse.json([])),
      // AuthContext.login() llama /auth/me tras cada login exitoso (Fase 3,
      // D2) — default handler acá para que los tests que no lo pisan no
      // revienten con un request sin mockear (onUnhandledRequest: "error").
      http.get(ME, () => HttpResponse.json({ id: 42, username: "usuario_test", rol: "Arbitro" })),
    );
  });

  // TASK-036 (UX-02): sin sesión, una ruta protegida lleva al formulario
  // de login (antes: una tarjeta "Necesitás iniciar sesión" con un enlace).
  it("navegar directo a /torneo-admin sin sesión lleva al login, no crashea", () => {
    renderApp("/torneo-admin/torneos");
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
    expect(screen.getByText(/Iniciá sesión para seguir/)).toBeInTheDocument();
  });

  it("navegar directo a /arbitro sin sesión lleva al login, no crashea (Fase 3, D3 + Fase 4, D1)", () => {
    renderApp("/arbitro");
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  });

  it("tras iniciar sesión desde una ruta protegida, vuelve a esa ruta (TASK-036)", async () => {
    mockLogin("AdminGeneral");
    renderApp("/admin/usuarios");
    await iniciarSesion();
    expect(await screen.findByRole("heading", { name: "Usuarios" })).toBeInTheDocument();
  });

  it("TorneoAdmin logueado no puede entrar a /arbitro (D3: TorneoAdmin nunca estuvo en la lista)", async () => {
    mockLogin("TorneoAdmin");
    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());

    renderApp("/arbitro");
    // TASK-036 (UX-02): con sesión es "sin permiso", no "iniciá sesión".
    expect(screen.getByRole("heading", { name: "No tenés permiso para ver esta página" })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Iniciar sesión" })).not.toBeInTheDocument();
  });

  it("AdminGeneral logueado SÍ puede entrar a /arbitro (Fase 4, D1: acceso cruzado)", async () => {
    mockLogin("AdminGeneral");
    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());

    renderApp("/arbitro");
    expect(await screen.findByRole("heading", { name: "Mis partidos" })).toBeInTheDocument();
  });

  it("navegar directo a /admin/usuarios sin sesión lleva al login (Fase 4, D4)", () => {
    renderApp("/admin/usuarios");
    expect(screen.getByRole("heading", { name: "Iniciar sesión" })).toBeInTheDocument();
  });

  it("TorneoAdmin logueado no puede entrar a /admin/usuarios (D4: literal AdminGeneral-only, coincide con el backend)", async () => {
    mockLogin("TorneoAdmin");
    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());

    renderApp("/admin/usuarios");
    expect(screen.getByRole("heading", { name: "No tenés permiso para ver esta página" })).toBeInTheDocument();
    expect(screen.getByText("AdminGeneral", { selector: "strong" })).toBeInTheDocument();
    // El enlace lleva al inicio de SU rol.
    expect(screen.getByRole("link", { name: "Ir a mi inicio" })).toHaveAttribute("href", "/torneo-admin");
  });

  it("AdminGeneral logueado puede entrar a /admin/usuarios (Fase 4, D4)", async () => {
    mockLogin("AdminGeneral");
    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());

    renderApp("/admin/usuarios");
    expect(await screen.findByRole("heading", { name: "Usuarios" })).toBeInTheDocument();
  });

  it("TorneoAdmin: login redirige a /torneo-admin (antes NO pasaba — login() no exponía el rol)", async () => {
    mockLogin("TorneoAdmin");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());
  });

  it("AdminGeneral: login también redirige a /torneo-admin", async () => {
    mockLogin("AdminGeneral");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());
  });

  it("Arbitro: login redirige a /arbitro, no a /dashboard ni /torneo-admin (Fase 3, D3)", async () => {
    mockLogin("Arbitro");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Mis partidos" })).toBeInTheDocument());
  });

  it("anónimo tipeando /dashboard directo lo sigue alcanzando (F20: se esconde el link, no la ruta)", async () => {
    renderApp("/dashboard");
    expect(await screen.findByRole("heading", { name: "Dashboard de Torneo" })).toBeInTheDocument();
  });

  it("anónimo no ve los links de Dashboard ni Control de Mesa en el NavBar (T1.1/T1.2, C7)", async () => {
    renderApp("/dashboard");
    await screen.findByRole("heading", { name: "Dashboard de Torneo" });
    expect(screen.queryByRole("link", { name: "Dashboard" })).not.toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Control de Mesa" })).not.toBeInTheDocument();
  });

  it("Arbitro logueado ve el link a Control de Mesa (T1.1, C7)", async () => {
    mockLogin("Arbitro");
    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Mis partidos" })).toBeInTheDocument());
    expect(screen.getByRole("link", { name: "Control de Mesa" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Dashboard" })).toBeInTheDocument();
    // D6: sin esto, T1.2 (esconder Dashboard al anónimo) + C16 ("/"
    // redirige a /dashboard con sesión) dejaban a CUALQUIER logueado sin
    // ningún link de vuelta al portal público.
    expect(screen.getByRole("link", { name: "Portal público" })).toBeInTheDocument();
  });

  // TASK-040 (FUN-12): el enlace apuntaba a "/", que con sesión redirige
  // al dashboard — hacer clic no llevaba al portal.
  it("con sesión, el enlace Portal público muestra el feed y no el dashboard", async () => {
    disciplinasDisponibles();
    sembrarSesion("TorneoAdmin", 3);
    renderApp("/torneo-admin");
    const user = userEvent.setup();

    await user.click(await screen.findByRole("link", { name: "Portal público" }));

    expect(await screen.findByRole("heading", { name: /partidos/i })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Dashboard de Torneo" })).not.toBeInTheDocument();
  });

  // TASK-036 (FE-03): antes el catch-all redirigía a "/" en silencio.
  it("una ruta inexistente muestra la 404; el anónimo vuelve al portal", async () => {
    disciplinasDisponibles();
    renderApp("/esto-no-existe");
    expect(screen.getByRole("heading", { name: "No encontramos esta página" })).toBeInTheDocument();
    expect(screen.getByText("/esto-no-existe")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir al portal" })).toHaveAttribute("href", "/");
  });

  it("la 404 con sesión ofrece volver al inicio del rol", async () => {
    disciplinasDisponibles();
    sembrarSesion("Arbitro", 7);
    renderApp("/torneo-admin/no-existe");
    expect(screen.getByRole("heading", { name: "No encontramos esta página" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Ir a mi inicio" })).toHaveAttribute("href", "/arbitro");
  });

  it("T5.5: /torneos/:torneoId monta la vista pública de torneo, sin sesión", async () => {
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/torneos/7", () =>
        HttpResponse.json({ id: 7, torneo_grupo_id: 1, formato: "Liga", fecha_inicio: "2099-01-01", estado: "Activo" }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/torneo-grupos/1", () =>
        HttpResponse.json({ id: 1, nombre: "Torneo Público Test", pais: null, logo_url: null }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/7/posiciones", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/7/resultados", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/estadisticas/torneos/7/goleadores", () => HttpResponse.json([])),
    );
    renderApp("/torneos/7");
    expect(await screen.findByRole("heading", { name: "Torneo Público Test" })).toBeInTheDocument();
  });

  it("T4.1/C16: \"/\" para anónimo muestra el feed público, no un redirect a /dashboard", async () => {
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/partidos/feed", () =>
        HttpResponse.json({ fecha_pedida: "2026-09-15", fecha_efectiva: "2026-09-15", total_disponible: 0, partidos: [] }),
      ),
      http.get("http://127.0.0.1:8000/api/v1/disciplinas/con-partidos", () => HttpResponse.json([])),
    );
    renderApp("/");
    expect(await screen.findByText("Actualizado", { exact: false })).toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Dashboard de Torneo" })).not.toBeInTheDocument();
  });

  it("T4.1/C16: \"/\" con sesión sigue redirigiendo a /dashboard — el arranque de un usuario logueado no cambia", async () => {
    mockLogin("AdminGeneral");
    renderApp("/login");
    await iniciarSesion();
    await waitFor(() => expect(screen.getByRole("heading", { name: "Torneo Admin" })).toBeInTheDocument());

    renderApp("/");
    expect(await screen.findByRole("heading", { name: "Dashboard de Torneo" })).toBeInTheDocument();
  });

  it("el fallo de GET /auth/me tras el login no rompe el login ni el redirect por rol", async () => {
    // Fase 3, D2: /auth/me se pide aparte del login para tener el id. Si
    // esa llamada falla, el login ya fue exitoso (login() usa el rol que
    // SÍ vino de /auth/login) — el redirect no depende de session.id.
    server.use(http.get(ME, () => HttpResponse.error()));
    mockLogin("Arbitro");
    renderApp("/login");

    await iniciarSesion();

    await waitFor(() => expect(screen.getByRole("heading", { name: "Mis partidos" })).toBeInTheDocument());
    // Sin id, "Mis partidos" no puede armar el filtro — se lo dice al
    // usuario en vez de pedir partidos sin filtrar o crashear.
    expect(
      screen.getByText(/No pudimos confirmar tu usuario/),
    ).toBeInTheDocument();
  });

  it("GET /auth/me se reintenta una vez: un fallo puntual no deja la sesión sin id (TASK-036)", async () => {
    let llamadas = 0;
    server.use(
      http.get(ME, () => {
        llamadas += 1;
        return llamadas === 1 ? HttpResponse.error() : HttpResponse.json({ id: 42, username: "usuario_test", rol: "Arbitro" });
      }),
    );
    mockLogin("Arbitro");
    renderApp("/login");
    await iniciarSesion();

    expect(await screen.findByText("No tenés partidos asignados por ahora.")).toBeInTheDocument();
    expect(screen.queryByText(/No pudimos confirmar tu usuario/)).not.toBeInTheDocument();
    expect(llamadas).toBe(2);
  });

  it("sin id tras los dos intentos, 'Mis partidos' ofrece reintentar (TASK-036)", async () => {
    let responde = false;
    server.use(
      http.get(ME, () =>
        responde ? HttpResponse.json({ id: 42, username: "usuario_test", rol: "Arbitro" }) : HttpResponse.error(),
      ),
    );
    mockLogin("Arbitro");
    renderApp("/login");
    await iniciarSesion();
    expect(await screen.findByText(/No pudimos confirmar tu usuario/)).toBeInTheDocument();

    responde = true;
    await userEvent.setup().click(screen.getByRole("button", { name: "Reintentar" }));

    expect(await screen.findByText("No tenés partidos asignados por ahora.")).toBeInTheDocument();
    expect(screen.queryByText(/No pudimos confirmar tu usuario/)).not.toBeInTheDocument();
  });
});

describe("Barra de navegación (TASK-036, UX-01)", () => {
  beforeEach(() => {
    server.use(
      http.get(TORNEOS, () => HttpResponse.json([])),
      http.get(PARTIDOS, () => HttpResponse.json([])),
      http.get(USUARIOS, () => HttpResponse.json([])),
    );
    disciplinasDisponibles();
  });

  it("Usuarios, Accesos y Auditoría van agrupados en 'Administración'", async () => {
    sembrarSesion("AdminGeneral", 1);
    const user = userEvent.setup();
    renderApp("/dashboard");

    const grupo = screen.getByRole("button", { name: /Administración/ });
    expect(grupo).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByRole("link", { name: "Usuarios" })).not.toBeInTheDocument();

    await user.click(grupo);
    expect(grupo).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("link", { name: "Accesos" })).toBeInTheDocument();

    // Elegir un enlace cierra el grupo.
    await user.click(screen.getByRole("link", { name: "Usuarios" }));
    expect(await screen.findByRole("heading", { name: "Usuarios" })).toBeInTheDocument();
    expect(grupo).toHaveAttribute("aria-expanded", "false");
  });

  it("Escape cierra el grupo y devuelve el foco a su botón", async () => {
    sembrarSesion("AdminGeneral", 1);
    const user = userEvent.setup();
    renderApp("/dashboard");
    const grupo = screen.getByRole("button", { name: /Administración/ });
    await user.click(grupo);
    await user.keyboard("{Escape}");
    expect(grupo).toHaveAttribute("aria-expanded", "false");
    expect(grupo).toHaveFocus();
  });

  it("el botón 'Menú' abre y cierra la navegación con aria-expanded", async () => {
    sembrarSesion("TorneoAdmin", 2);
    const user = userEvent.setup();
    renderApp("/dashboard");
    const menu = screen.getByRole("button", { name: "Menú" });
    expect(menu).toHaveAttribute("aria-controls", "nav-principal");
    expect(menu).toHaveAttribute("aria-expanded", "false");
    await user.click(menu);
    expect(screen.getByRole("button", { name: "Cerrar menú" })).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("navigation", { name: "Principal" })).toHaveClass("nav-bar__links--abierto");
  });

  it("los roles sin Administración no ven el grupo", () => {
    sembrarSesion("TorneoAdmin", 2);
    renderApp("/dashboard");
    expect(screen.queryByRole("button", { name: /Administración/ })).not.toBeInTheDocument();
  });
});

// --- Licencia revocada a mitad de sesión (rbac-licencias-torneos-plan.md, §5.2) ---

describe("LicenseRevokedScreen (rbac-licencias-torneos-plan.md, §5.2)", () => {
  beforeEach(() => {
    server.use(
      http.get(TORNEOS, () => HttpResponse.json([])),
      http.get(PARTIDOS, () => HttpResponse.json([])),
      http.get(USUARIOS, () => HttpResponse.json([])),
      http.get(ME, () => HttpResponse.json({ id: 42, username: "usuario_test", rol: "TorneoAdmin" })),
    );
  });

  // /dashboard (Dashboard.tsx) hace GET /api/v1/torneos directo, sin pasar
  // por RequireRole — es pública, pero el interceptor de client.ts aplica
  // a CUALQUIER response, sesión o no. Se usa acá en vez de
  // /torneo-admin/torneos porque esa pantalla en realidad consulta
  // /api/v1/torneo-grupos, no /api/v1/torneos (verificado en el código,
  // no asumido).
  it("un 403 con X-License-Revoked reemplaza el shell entero, sin importar la ruta activa", async () => {
    sembrarSesion("TorneoAdmin", 42);
    server.use(
      http.get(TORNEOS, () =>
        HttpResponse.json(
          { detail: "Licencia inactiva o revocada. Contactá al administrador." },
          { status: 403, headers: { "X-License-Revoked": "true" } },
        ),
      ),
    );

    renderApp("/dashboard");

    expect(await screen.findByText("Licencia Inactiva o Revocada")).toBeInTheDocument();
    expect(screen.getByText("Contacte al administrador.")).toBeInTheDocument();
    // El shell normal (Dashboard) ya no está — la pantalla de bloqueo
    // reemplaza TODO, no solo el contenido de la ruta.
    expect(screen.queryByRole("heading", { name: "Dashboard de Torneo" })).not.toBeInTheDocument();
  });

  it("un 403 genérico (rol insuficiente) NO dispara la pantalla de licencia", async () => {
    sembrarSesion("TorneoAdmin", 42);
    server.use(
      http.get(TORNEOS, () =>
        HttpResponse.json({ detail: "Esta operación requiere TorneoAdmin o AdminGeneral." }, { status: 403 }),
      ),
    );

    renderApp("/dashboard");

    await waitFor(() => expect(screen.getByRole("heading", { name: "Dashboard de Torneo" })).toBeInTheDocument());
    expect(screen.queryByText("Licencia Inactiva o Revocada")).not.toBeInTheDocument();
  });
});
