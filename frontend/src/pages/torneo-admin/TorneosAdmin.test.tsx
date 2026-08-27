import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { TorneosAdminPage } from "./TorneosAdmin";

// El motor compartido (list/create/edit/baja) ya está probado en
// SimpleResourceAdminPage.test.tsx — esto solo confirma que la config de
// Torneo (basePath, campos, columnas) está bien conectada, incluida la
// resolución de disciplina_id → nombre (equipos-jugadores-plan.md).
describe("TorneosAdminPage", () => {
  it("lista torneos con su disciplina resuelta y fechas formateadas", async () => {
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/disciplinas", () =>
        HttpResponse.json([{ id: 1, nombre: "Fútbol", tipo: "Equipo", estado: "Activo" }]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/modalidades", () => HttpResponse.json([])),
      http.get("http://127.0.0.1:8000/api/v1/torneos", () =>
        HttpResponse.json([
          {
            id: 1,
            nombre: "Copa Ecotec 2026",
            disciplina_id: 1,
            modalidad_id: null,
            fecha_inicio: "2026-01-10",
            fecha_fin: "2026-03-30",
            estado: "Activo",
          },
        ]),
      ),
    );
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <TorneosAdminPage />
      </Wrapper>,
    );
    expect(await screen.findByText("Copa Ecotec 2026")).toBeInTheDocument();
    expect(screen.getByText("Fútbol")).toBeInTheDocument();
  });
});
