import { render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { EquiposAdminPage } from "./EquiposAdmin";

describe("EquiposAdminPage", () => {
  it("lista equipos", async () => {
    server.use(
      http.get("http://127.0.0.1:8000/api/v1/equipos", () =>
        HttpResponse.json([{ id: 1, nombre: "Tiburones FC", estado: "Activo" }]),
      ),
    );
    const Wrapper = createWrapper();
    render(
      <Wrapper>
        <EquiposAdminPage />
      </Wrapper>,
    );
    expect(await screen.findByText("Tiburones FC")).toBeInTheDocument();
  });
});
