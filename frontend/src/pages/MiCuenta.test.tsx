import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { TOKEN_STORAGE_KEY } from "../api/client";
import { server } from "../test/msw-server";
import { createWrapper } from "../test/test-utils";
import { MiCuentaPage } from "./MiCuenta";

const RUTA = "http://127.0.0.1:8000/api/v1/auth/cambiar-password";

// TASK-033: pantalla "Mi cuenta".
describe("MiCuentaPage", () => {
  beforeEach(() => {
    localStorage.setItem(TOKEN_STORAGE_KEY, "token-viejo");
    localStorage.setItem("score-app.session", JSON.stringify({ username: "admin", rol: "AdminGeneral", id: 1 }));
  });

  async function completar(actual: string, nueva: string, repetir = nueva) {
    const user = userEvent.setup();
    render(<MiCuentaPage />, { wrapper: createWrapper() });
    await user.type(screen.getByLabelText("Contraseña actual"), actual);
    await user.type(screen.getByLabelText("Contraseña nueva"), nueva);
    await user.type(screen.getByLabelText("Repetir contraseña nueva"), repetir);
    return user;
  }

  it("cambia la contraseña y guarda el token nuevo", async () => {
    let cuerpo: unknown = null;
    server.use(
      http.post(RUTA, async ({ request }) => {
        cuerpo = await request.json();
        return HttpResponse.json({ access_token: "token-nuevo", token_type: "bearer", rol: "AdminGeneral" });
      }),
    );
    const user = await completar("admin1234", "una-clave-nueva-larga");
    await user.click(screen.getByRole("button", { name: "Cambiar contraseña" }));

    expect(await screen.findByRole("status")).toHaveTextContent("Contraseña actualizada");
    expect(cuerpo).toEqual({ password_actual: "admin1234", password_nueva: "una-clave-nueva-larga" });
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe("token-nuevo");
    expect(screen.getByLabelText("Contraseña actual")).toHaveValue("");
  });

  it("muestra el error del backend si la actual es incorrecta", async () => {
    server.use(http.post(RUTA, () => HttpResponse.json({ detail: "La contraseña actual no es correcta." }, { status: 400 })));
    const user = await completar("equivocada", "una-clave-nueva-larga");
    await user.click(screen.getByRole("button", { name: "Cambiar contraseña" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("La contraseña actual no es correcta.");
    expect(localStorage.getItem(TOKEN_STORAGE_KEY)).toBe("token-viejo");
  });

  it("no envía si la nueva es corta o la confirmación no coincide", async () => {
    let llamadas = 0;
    server.use(
      http.post(RUTA, () => {
        llamadas += 1;
        return HttpResponse.json({});
      }),
    );
    await completar("admin1234", "corta", "corta");
    expect(screen.getByText(/al menos 10 caracteres/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cambiar contraseña" })).toBeDisabled();

    await waitFor(() => expect(llamadas).toBe(0));
  });

  it("avisa si la confirmación no coincide", async () => {
    await completar("admin1234", "una-clave-nueva-larga", "otra-clave-distinta");
    expect(screen.getByText("La confirmación no coincide con la contraseña nueva.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cambiar contraseña" })).toBeDisabled();
  });
});
