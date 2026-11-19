import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../../api/client";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { CatalogoDisciplinasPage } from "./CatalogoDisciplinas";

const SESSION_STORAGE_KEY = "score-app.session";
const CATALOGO = "http://127.0.0.1:8000/api/v1/disciplinas/con-modalidades";

function sembrarSesion(rol: string) {
  localStorage.setItem(TOKEN_STORAGE_KEY, "fake-token");
  localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify({ username: "u", rol, id: 1 }));
}

function renderPagina() {
  const Wrapper = createWrapper();
  render(
    <Wrapper>
      <CatalogoDisciplinasPage />
    </Wrapper>,
  );
}

// TASK-013 (SEC-04): disciplinas y modalidades son un catálogo de sistema,
// solo AdminGeneral las activa o desactiva (el backend responde 403 al resto).
describe("CatalogoDisciplinasPage — permisos (TASK-013)", () => {
  beforeEach(() => {
    server.use(
      http.get(CATALOGO, () =>
        HttpResponse.json([
          {
            id: 1,
            nombre: "Fútbol",
            estado: "Activo",
            modalidades: [{ id: 1, nombre: "Fútbol 11", tamano_equipo: 11, estado: "Activo", disciplina_id: 1 }],
          },
        ]),
      ),
    );
  });

  it("AdminGeneral ve los controles de activar/desactivar", async () => {
    sembrarSesion("AdminGeneral");
    renderPagina();
    expect(await screen.findByRole("button", { name: "Desactivar disciplina" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Desactivar" })).toBeInTheDocument();
  });

  it("TorneoAdmin ve el catálogo sin controles y con la explicación", async () => {
    sembrarSesion("TorneoAdmin");
    renderPagina();
    expect(await screen.findByText("Fútbol 11")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Desactivar/ })).not.toBeInTheDocument();
    expect(screen.getByText(/Solo un Admin General/)).toBeInTheDocument();
  });
});
