import { expect, test } from "@playwright/test";
import {
  cargarPlantilla,
  conSesion,
  crearCuenta,
  crearEquipos,
  crearTorneo,
  get,
  inscribir,
  loginAdmin,
  post,
  unico,
  type Partido,
} from "./api";

/** PR-062: resultado directo de una semifinal empatada que se define por
 * penales; el ganador avanza en la llave. */
test("empate 1-1 y penales 4-3: el local pasa a la final", async ({ page }) => {
  const admin = await loginAdmin();
  const org = await crearCuenta(admin, "TorneoAdmin", "org062");
  const torneo = await crearTorneo(org, unico("Copa Penales"), "Eliminacion");
  const equipos = await crearEquipos(org, [unico("Halcones"), unico("Linces"), unico("Toros"), unico("Osos")]);
  const inscripciones = await inscribir(org, torneo.id, equipos.map((e) => e.id));
  for (const [i, insc] of inscripciones.entries()) await cargarPlantilla(org, insc, `J${i}`, 2);
  await post(`/torneos/${torneo.id}/sorteo`, org, {});

  const llave = await get<Partido[]>(`/torneos/${torneo.id}/bracket`, org);
  const semi = llave.find((p) => p.equipos_id_local != null && p.equipos_id_visitante != null);
  if (!semi) throw new Error("el sorteo no dejó ninguna semifinal con los dos equipos");
  const nombre = (id: number | null) => equipos.find((e) => e.id === id)!.nombre;
  const local = nombre(semi.equipos_id_local);
  const visitante = nombre(semi.equipos_id_visitante);

  await conSesion(page, org);
  await page.goto(`/control-de-mesa/partido/${semi.id}`);
  await page.getByRole("button", { name: "Cargar resultado directo" }).click();
  const modal = page.getByRole("dialog", { name: "Cargar resultado directo" });

  await modal.getByLabel(`Goles ${local}`).fill("1");
  await modal.getByLabel(`Goles ${visitante}`).fill("1");
  await modal.getByLabel(`Goleador, ${local} #1`).selectOption({ index: 1 });
  // El primer jugador del visitante: la segunda opción de su grupo.
  const opcionesVisitante = modal.getByLabel(`Goleador, ${visitante} #1`).locator(`optgroup[label="${visitante}"] option`);
  await modal.getByLabel(`Goleador, ${visitante} #1`).selectOption(await opcionesVisitante.first().getAttribute("value"));
  await modal.getByLabel(`Minuto, ${local} #1`).fill("30");
  await modal.getByLabel(`Minuto, ${visitante} #1`).fill("75");

  await expect(modal.getByText("Empate en el marcador — tanda de penales")).toBeVisible();
  await modal.getByLabel(local, { exact: true }).fill("4");
  await modal.getByLabel(visitante, { exact: true }).fill("3");
  await expect(modal.getByText(`Penales 4-3 — avanza ${local}.`)).toBeVisible();
  await modal.getByRole("button", { name: "Guardar resultado" }).click();
  await expect(modal).toBeHidden();

  // La llave: el ganador sigue en la final y el perdedor, en el tercer
  // puesto (los dos aparecen dos veces: semifinal y partido siguiente).
  await page.goto(`/torneo-admin/torneos/${torneo.id}/partidos`);
  await expect(page.getByLabel("Penales 4 a 3")).toBeVisible();
  await expect(page.locator(".bracket__equipo", { hasText: local })).toHaveCount(2);
  await expect(page.locator(".bracket__equipo", { hasText: visitante })).toHaveCount(2);

  const despues = await get<(Partido & { ronda_nombre: string | null })[]>(`/torneos/${torneo.id}/bracket`, org);
  const enLaFinal = despues.find(
    (p) => p.ronda_nombre === "Final" && [p.equipos_id_local, p.equipos_id_visitante].includes(semi.equipos_id_local),
  );
  expect(enLaFinal, "el ganador por penales no quedó en la final").toBeTruthy();
});
