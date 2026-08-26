import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { JugadoresAdminPage } from "./JugadoresAdmin";

describe("JugadoresAdminPage", () => {
  it("lista jugadores", async () => {
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/jugadores", () =>
        HttpResponse.json([{ id: 1, nombre: "Carlos Pérez", estado: "Activo" }]),
      ),
    );
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <JugadoresAdminPage />
      </Wrapper>,
    );
    expect(await screen.findByText("Carlos Pérez")).toBeInTheDocument();
  });
});
