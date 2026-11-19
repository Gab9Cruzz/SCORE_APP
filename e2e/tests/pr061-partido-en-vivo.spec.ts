import { expect, test, type Page } from "@playwright/test";
import {
  cargarPlantilla,
  conSesion,
  crearCuenta,
  crearEquipos,
  crearTorneo,
  FUTBOL_5,
  inscribir,
  loginAdmin,
  partidosDe,
  patch,
  post,
  unico,
} from "./api";

/** Convoca los seis del equipo: cinco titulares (por dorsal) y uno al banco. */
async function alinear(page: Page, equipo: string) {
  await page.getByRole("tab", { name: new RegExp(equipo) }).click();
  await page.getByRole("button", { name: /Paso 1 · Convocados/ }).click();
  for (let i = 1; i <= 6; i++) {
    const casilla = page.getByRole("checkbox", { name: new RegExp(`#${i} `) });
    if (!(await casilla.isChecked())) await casilla.check();
  }
  await page.getByRole("button", { name: /^Listo, \d+ convocados$/ }).click();
  await page.getByRole("button", { name: "Marcar 5 por dorsal" }).click();
  await expect(page.getByText("5 de 5 ✓")).toBeVisible();
  await page.getByRole("button", { name: "Guardar alineación" }).click();
  await expect(page.getByRole("button", { name: "Guardar alineación" })).toBeDisabled();
}

/** Un evento por el tablero de "Cargar evento": tipo → equipo → jugador. */
async function cargar(page: Page, tipo: RegExp, equipo: string, jugador: string) {
  const panel = page.locator(".carga-evento");
  await panel.getByRole("button", { name: tipo }).click();
  await panel.getByRole("button", { name: equipo, exact: true }).click();
  await panel.getByRole("button", { name: jugador }).click();
  await expect(panel.getByText(/Minuto \d+'/)).toBeVisible();
  await panel.getByRole("button", { name: "Confirmar" }).click();
  await expect(panel.getByRole("button", { name: /Tarjeta Amarilla$/ })).toBeVisible();
}

/** PR-061: partido en vivo — alineación, inicio, gol, doble amarilla,
 * cambio y fin; el portal muestra el marcador y la tabla correctos. */
test("del vestuario al pitazo final, y el portal lo refleja", async ({ page, browser }) => {
  const admin = await loginAdmin();
  const org = await crearCuenta(admin, "TorneoAdmin", "org061");
  const nombreTorneo = unico("Liga Vivo");
  const torneo = await crearTorneo(org, nombreTorneo, "Liga", {}, FUTBOL_5);
  const [local, visitante] = await crearEquipos(org, [unico("Rayos"), unico("Truenos")], FUTBOL_5);
  const [inscLocal, inscVisitante] = await inscribir(org, torneo.id, [local.id, visitante.id]);
  await cargarPlantilla(org, inscLocal, "Rayo", 6);
  await cargarPlantilla(org, inscVisitante, "Trueno", 6);
  await post(`/torneos/${torneo.id}/fixture`, org);
  await patch(`/torneos/${torneo.id}`, org, { publicado: true });
  const [partido] = await partidosDe(org, torneo.id);

  await conSesion(page, org);
  await page.goto(`/control-de-mesa/partido/${partido.id}`);
  const nombreLocal = partido.equipos_id_local === local.id ? local.nombre : visitante.nombre;
  const nombreVisitante = partido.equipos_id_local === local.id ? visitante.nombre : local.nombre;
  await alinear(page, nombreLocal);
  await alinear(page, nombreVisitante);

  await page.getByRole("button", { name: "▶ Empezar Partido" }).click();
  await expect(page.getByRole("heading", { name: "Cargar evento" })).toBeVisible();

  // Gol del local.
  const goleador = nombreLocal.startsWith("Rayos") ? "Rayo" : "Trueno";
  const rival = goleador === "Rayo" ? "Trueno" : "Rayo";
  await cargar(page, /Gol$/, nombreLocal, `#3 ${goleador} 3`);
  await expect(page.getByText(/1\s*-\s*0/).first()).toBeVisible();

  // Doble amarilla al mismo jugador visitante: la segunda genera la roja.
  await cargar(page, /Tarjeta Amarilla$/, nombreVisitante, `#4 ${rival} 4`);
  await cargar(page, /Tarjeta Amarilla$/, nombreVisitante, `#4 ${rival} 4`);
  const eventos = page.locator("section", { has: page.getByRole("heading", { name: "Eventos cargados" }) });
  await expect(eventos.getByRole("listitem", { name: /Tarjeta Amarilla/ })).toHaveCount(2);
  await expect(eventos.getByRole("listitem", { name: /Tarjeta Roja/ })).toHaveCount(1);

  // Cambio en el local: sale el 2, entra el 6 (el suplente).
  const enVivo = page.locator("section", { has: page.getByRole("heading", { name: "Alineación en vivo" }) });
  const fila = enVivo.getByRole("listitem").filter({ hasText: `#2 ${goleador} 2` });
  await fila.getByRole("button", { name: "Sacar" }).click();
  await page.getByRole("dialog").getByRole("button", { name: new RegExp(`${goleador} 6`) }).click();
  await expect(page.getByRole("dialog")).toBeHidden();
  await expect(enVivo.getByText(`#6 ${goleador} 6`)).toBeVisible();

  // Fin: entretiempo, segundo tiempo y pitazo final.
  await page.getByRole("button", { name: "Fin 1er Tiempo" }).click();
  await page.getByRole("button", { name: "▶ Iniciar 2do Tiempo" }).click();
  await page.getByRole("button", { name: "Fin del Partido" }).click();
  await expect(page.getByText("Finalizado").first()).toBeVisible();

  // --- Portal, como visitante.
  const visitanteWeb = await browser.newPage();
  await visitanteWeb.goto(`/partidos/${partido.id}`);
  const marcadorPublico = visitanteWeb.locator(".marcador");
  await expect(marcadorPublico).toContainText(nombreLocal);
  await expect(marcadorPublico.locator(".marcador__score")).toHaveText(/1\s*-\s*0/);
  await expect(visitanteWeb.locator(".marcador__estado")).toContainText(/Finalizado/i);

  await visitanteWeb.goto(`/torneos/${torneo.id}`);
  await expect(visitanteWeb.getByText("1 - 0")).toBeVisible(); // pestaña Resultados
  await visitanteWeb.getByText("Posiciones", { exact: true }).click();
  const tabla = visitanteWeb.getByRole("region", { name: "Tabla de posiciones" });
  // Equipo | PJ | PG | PE | PP | GF | GC | DG | Pts
  await expect(tabla.getByRole("row", { name: new RegExp(`${nombreLocal}.*1 1 0 0 1 0 1 3$`) })).toBeVisible();
  await expect(tabla.getByRole("row", { name: new RegExp(`${nombreVisitante}.*1 0 0 1 0 1 -1 0$`) })).toBeVisible();
  await visitanteWeb.close();
});
