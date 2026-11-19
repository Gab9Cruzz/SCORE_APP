import { expect, test } from "@playwright/test";
import { cargarPlantilla, conSesion, crearCuenta, crearEquipos, crearTorneo, inscribir, loginAdmin, unico } from "./api";

/** PR-060: alta completa — torneo, tres equipos, plantillas por lote y
 * fixture. El fixture aparece en el panel y, recién después de publicar, en
 * el portal. */
test("de la inscripción al fixture publicado", async ({ page, browser }) => {
  const admin = await loginAdmin();
  const org = await crearCuenta(admin, "TorneoAdmin", "org060");
  const nombreTorneo = unico("Liga Alta");
  const torneo = await crearTorneo(org, nombreTorneo, "Liga");
  const equipos = await crearEquipos(org, [unico("Cóndores"), unico("Pumas"), unico("Jaguares")]);
  const inscripciones = await inscribir(org, torneo.id, equipos.map((e) => e.id));
  // Dos plantillas por la API; la tercera se carga en la pantalla.
  await cargarPlantilla(org, inscripciones[1], "Puma", 3);
  await cargarPlantilla(org, inscripciones[2], "Jaguar", 3);

  await conSesion(page, org);

  // --- Plantilla por lote, en la pantalla, para el primer equipo.
  await page.goto(`/torneo-admin/torneos/${torneo.id}/plantillas`);
  await page.getByRole("button", { name: "+ Registro por lote" }).click();
  await expect(page.getByRole("heading", { name: "Registro por lote" })).toBeVisible();
  await page.getByLabel("Equipo").selectOption({ label: equipos[0].nombre });
  await page.getByLabel("Fecha de inicio").fill("2026-01-01");
  const marca = Date.now().toString(36);
  for (let i = 1; i <= 2; i++) {
    if (i > 1) await page.getByRole("button", { name: "+ agregar fila" }).click();
    await page.getByLabel(`Cédula fila ${i}`).fill(`L${marca}${i}`);
    await page.getByLabel(`Nombre fila ${i}`).fill(`Cóndor ${i}`);
    await page.getByLabel(`Dorsal fila ${i}`).fill(String(i));
    await page.getByLabel(`Correo fila ${i}`).fill(`condor${i}.${marca}@example.com`);
  }
  await page.getByRole("button", { name: "Validar" }).click();
  await expect(page.getByRole("heading", { name: "✅ Válidos (2)" })).toBeVisible();
  await page.getByRole("button", { name: "Confirmar" }).click();
  await expect(page.getByText("2 jugador(es) registrado(s).")).toBeVisible();

  // --- Fixture desde el panel del torneo.
  await page.goto(`/torneo-admin/torneos/${torneo.id}/partidos`);
  await page.getByRole("button", { name: "Generar Fixture" }).click();
  // Liga de tres a una vuelta: tres partidos, cada equipo en dos.
  const tabla = page.getByRole("table").filter({ hasText: equipos[0].nombre });
  await expect(tabla.getByRole("row").filter({ hasText: " vs " })).toHaveCount(3);
  for (const e of equipos) await expect(tabla.getByText(e.nombre).first()).toBeVisible();

  // --- Portal: sin publicar, un visitante no lo encuentra.
  const visitante = await browser.newPage();
  await visitante.goto(`/torneos/${torneo.id}`);
  await expect(visitante.getByText(/no (existe|está disponible)|no encontramos/i).first()).toBeVisible();

  // --- Publicar desde la lista de torneos.
  await page.goto("/torneo-admin/torneos");
  const tarjeta = page.locator(".tarjeta-torneo").filter({ hasText: nombreTorneo });
  await tarjeta.getByRole("button", { name: "Publicar" }).click();
  await expect(tarjeta.getByText("🟢 Publicado")).toBeVisible();

  // --- Ahora el visitante ve el torneo y su fixture.
  await visitante.reload();
  await expect(visitante.getByRole("heading", { name: nombreTorneo })).toBeVisible();
  for (const e of equipos) await expect(visitante.getByText(e.nombre).first()).toBeVisible();
  await visitante.close();
});
