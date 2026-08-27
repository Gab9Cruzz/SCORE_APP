import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { ModalidadesAdminPage } from "./ModalidadesAdmin";

describe("ModalidadesAdminPage", () => {
  it("lista modalidades con su disciplina resuelta", async () => {
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/disciplinas", () =>
        HttpResponse.json([{ id: 1, nombre: "Tenis", tipo: "Individual", estado: "Activo" }]),
      ),
      http.get("http://127.0.0.1:8000/api/v1/modalidades", () =>
        HttpResponse.json([{ id: 1, disciplina_id: 1, nombre: "Dobles", tamano_equipo: 2, estado: "Activo" }]),
      ),
    );
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <ModalidadesAdminPage />
      </Wrapper>,
    );
    expect(await screen.findByText("Dobles")).toBeInTheDocument();
    expect(screen.getByText("Tenis")).toBeInTheDocument();
  });
});
