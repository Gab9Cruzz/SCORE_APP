import { expect, test } from "@playwright/test";
import { conSesion, crearCuenta, crearEquipos, crearTorneo, inscribir, loginAdmin, patch, post, unico } from "./api";

/** PR-063: cada rol ve lo que le corresponde. */

test("árbitro: entra por el formulario, ve sus partidos y no la administración", async ({ page }) => {
  const admin = await loginAdmin();
  const arbitro = await crearCuenta(admin, "Arbitro", "arb");

  await page.goto("/login");
  await page.getByLabel("Usuario").fill(arbitro.username);
  await page.getByLabel("Contraseña").fill(arbitro.password);
  await page.getByRole("button", { name: "Ingresar" }).click();

  await expect(page).toHaveURL(/\/arbitro$/);
  await expect(page.getByRole("heading", { name: "Mis partidos" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Torneo Admin" })).toHaveCount(0);

  await page.goto("/torneo-admin/torneos");
  await expect(page.getByRole("heading", { name: "No tenés permiso para ver esta página" })).toBeVisible();
  await expect(page.getByText(`Tu cuenta (${arbitro.username}) es`)).toBeVisible();
});

test("TorneoAdmin sin torneos asignados no ve los torneos de otro", async ({ page }) => {
  const admin = await loginAdmin();
  const duenio = await crearCuenta(admin, "TorneoAdmin", "org");
  const ajeno = await crearCuenta(admin, "TorneoAdmin", "orgsin");
  const nombre = unico("Copa Ajena");
  const torneo = await crearTorneo(duenio, nombre, "Liga");
  const equipos = await crearEquipos(duenio, [unico("Ajeno A"), unico("Ajeno B")]);
  await inscribir(duenio, torneo.id, equipos.map((e) => e.id));
  await post(`/torneos/${torneo.id}/fixture`, duenio);

  await conSesion(page, ajeno);
  await page.goto("/torneo-admin/torneos");
  await expect(page.getByRole("heading", { name: "Torneo Admin" })).toBeVisible();
  await expect(page.getByText(nombre)).toHaveCount(0);

  // Control de Mesa: los partidos del otro tampoco aparecen.
  await page.goto("/control-de-mesa");
  await expect(page.getByRole("heading", { name: "Control de Mesa" })).toBeVisible();
  await expect(page.getByText(equipos[0].nombre)).toHaveCount(0);

  // Y su dueño sí lo ve, para que la ausencia de arriba no sea casualidad.
  await page.context().clearCookies();
  const otra = await page.context().newPage();
  await conSesion(otra, duenio);
  await otra.goto("/torneo-admin/torneos");
  await expect(otra.getByText(nombre)).toBeVisible();
});

test("una cuenta con la licencia revocada pierde el acceso en la siguiente acción", async ({ page }) => {
  const admin = await loginAdmin();
  const org = await crearCuenta(admin, "TorneoAdmin", "orglic");

  await conSesion(page, org);
  await page.goto("/torneo-admin/torneos");
  await expect(page.getByRole("heading", { name: "Torneo Admin" })).toBeVisible();

  await patch(`/usuarios/${org.id}/licencia`, admin, { activa: false });

  // Las lecturas públicas siguen respondiendo (el backend trata el token
  // revocado como anónimo); el corte llega con la primera acción que exige
  // sesión válida: acá, crear un equipo.
  await page.getByRole("link", { name: "Equipos" }).click();
  await page.getByRole("button", { name: "+ Nuevo equipo" }).click();
  await page.getByLabel("Nombre").fill(unico("Sin licencia"));
  await page.getByLabel("Disciplina").selectOption({ label: "Fútbol" });
  await page.getByLabel("Categoría (modalidad)").selectOption({ index: 1 });
  await page.getByRole("button", { name: "Crear" }).click();

  await expect(page.getByRole("heading", { name: "Licencia Inactiva o Revocada" })).toBeVisible();
  // El shell normal (barra con Torneo Admin) desaparece por completo.
  await expect(page.getByRole("link", { name: "Torneo Admin" })).toHaveCount(0);
});
