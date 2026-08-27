import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { DisciplinasAdminPage } from "./DisciplinasAdmin";

describe("DisciplinasAdminPage", () => {
  it("lista disciplinas", async () => {
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/disciplinas", () =>
        HttpResponse.json([{ id: 1, nombre: "Fútbol", tipo: "Equipo", estado: "Activo" }]),
      ),
    );
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <DisciplinasAdminPage />
      </Wrapper>,
    );
    expect(await screen.findByText("Fútbol")).toBeInTheDocument();
    expect(screen.getByText("Equipo")).toBeInTheDocument();
  });
});
