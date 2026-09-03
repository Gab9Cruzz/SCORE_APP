import { http, HttpResponse } from "msw";
import { beforeEach, describe, expect, it } from "vitest";
import { server } from "../test/msw-server";
import { api, setOnLicenseRevoked, setOnUnauthorized } from "./client";

const TORNEOS = "http://127.0.0.1:8000/api/v1/torneos";

// rbac-licencias-torneos-plan.md, T14 (Eng review — IRON RULE de
// regresión): client.ts ya tenía la rama de 401 antes de este plan;
// agregar la de 403+licencia es una MODIFICACIÓN de código existente, no
// solo una adición. Estos tests prueban específicamente que las dos ramas
// no se pisan entre sí.
describe("client.ts — onLicenseRevoked / onUnauthorized (rbac-licencias-torneos-plan.md)", () => {
  beforeEach(() => {
    setOnLicenseRevoked(null);
    setOnUnauthorized(null);
  });

  it("un 403 CON el header X-License-Revoked dispara onLicenseRevoked", async () => {
    let disparado = false;
    setOnLicenseRevoked(() => {
      disparado = true;
    });
    server.use(
      http.get(TORNEOS, () =>
        HttpResponse.json(
          { detail: "Licencia inactiva o revocada. Contactá al administrador." },
          { status: 403, headers: { "X-License-Revoked": "true" } },
        ),
      ),
    );

    await api.GET("/api/v1/torneos", {});

    expect(disparado).toBe(true);
  });

  it("un 403 SIN el header (rol insuficiente genérico) NO dispara onLicenseRevoked — regresión", async () => {
    let disparado = false;
    setOnLicenseRevoked(() => {
      disparado = true;
    });
    server.use(
      http.get(TORNEOS, () =>
        HttpResponse.json({ detail: "Esta operación requiere TorneoAdmin o AdminGeneral." }, { status: 403 }),
      ),
    );

    await api.GET("/api/v1/torneos", {});

    expect(disparado).toBe(false);
  });

  it("un 401 sigue dispando onUnauthorized, sin pisar la rama de licencia", async () => {
    let licenciaDisparado = false;
    let unauthorizedDisparado = false;
    setOnLicenseRevoked(() => {
      licenciaDisparado = true;
    });
    setOnUnauthorized(() => {
      unauthorizedDisparado = true;
    });
    server.use(http.get(TORNEOS, () => HttpResponse.json({ detail: "Token inválido o expirado." }, { status: 401 })));

    await api.GET("/api/v1/torneos", {});

    expect(unauthorizedDisparado).toBe(true);
    expect(licenciaDisparado).toBe(false);
  });

  it("un 200 normal no dispara ninguno de los dos callbacks", async () => {
    let licenciaDisparado = false;
    let unauthorizedDisparado = false;
    setOnLicenseRevoked(() => {
      licenciaDisparado = true;
    });
    setOnUnauthorized(() => {
      unauthorizedDisparado = true;
    });
    server.use(http.get(TORNEOS, () => HttpResponse.json([])));

    await api.GET("/api/v1/torneos", {});

    expect(licenciaDisparado).toBe(false);
    expect(unauthorizedDisparado).toBe(false);
  });
});
