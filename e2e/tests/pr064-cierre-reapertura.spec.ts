import { expect, test } from "@playwright/test";
import {
  cargarPlantilla,
  conSesion,
  crearCuenta,
  crearEquipos,
  crearTorneo,
  ganar,
  get,
  inscribir,
  loginAdmin,
  post,
  unico,
  type Partido,
} from "./api";

type PartidoLlave = Partido & { ronda_nombre: string | null };

/** PR-064: corregir un resultado, cerrar el torneo, reabrirlo y volver a
 * cerrarlo, con el podio recalculado en cada paso.
 *
 * El orden difiere del enunciado ("cerrar, reabrir y corregir") a
 * propósito: por la decisión de TASK-009, un partido de llave cerrado no
 * se corrige anulando eventos, sino con un reclamo, y el reclamo solo
 * procede mientras el partido siguiente no empezó. Con el torneo cerrado
 * la final ya se jugó, así que la corrección va antes del cierre. */
test("un reclamo en semifinal cambia el podio; reabrir lo borra y cerrar lo recalcula", async ({ page }) => {
  const admin = await loginAdmin();
  const org = await crearCuenta(admin, "TorneoAdmin", "org064");
  const torneo = await crearTorneo(org, unico("Copa Cierre"), "Eliminacion");
  const equipos = await crearEquipos(org, [unico("Ciervos"), unico("Zorros"), unico("Gatos"), unico("Lobos")]);
  const inscripciones = await inscribir(org, torneo.id, equipos.map((e) => e.id));
  for (const [i, insc] of inscripciones.entries()) await cargarPlantilla(org, insc, `C${i}`, 2);
  await post(`/torneos/${torneo.id}/sorteo`, org, {});
  const nombre = (id: number | null) => equipos.find((e) => e.id === id)!.nombre;

  const llave = await get<PartidoLlave[]>(`/torneos/${torneo.id}/bracket`, org);
  const [semi1, semi2] = llave.filter((p) => p.ronda_nombre === "Semifinal");
  // En cancha ganan los dos locales.
  await ganar(org, torneo.id, semi1.id, semi1.equipos_id_local!);
  await ganar(org, torneo.id, semi2.id, semi2.equipos_id_local!);
  const perdedorEnCancha = semi1.equipos_id_visitante!;

  await conSesion(page, org);
  await page.goto(`/torneo-admin/torneos/${torneo.id}/partidos`);

  // --- Corrección: reclamo a favor del que perdió la primera semifinal.
  const tarjetaSemi = page.locator(".bracket__partido", { hasText: nombre(semi1.equipos_id_local) }).filter({
    hasText: nombre(semi1.equipos_id_visitante),
  });
  await tarjetaSemi.getByRole("button", { name: "Resolver reclamo" }).click();
  await tarjetaSemi.getByLabel("A favor de").selectOption({ label: nombre(perdedorEnCancha) });
  await tarjetaSemi.getByLabel("Motivo").fill("Alineación indebida del rival (e2e)");
  await tarjetaSemi.getByRole("button", { name: "Confirmar reclamo" }).click();
  await expect(tarjetaSemi.getByText(`avanza ${nombre(perdedorEnCancha)}`)).toBeVisible();

  // Final y tercer puesto, con los equipos que dejó el reclamo.
  const despues = await get<PartidoLlave[]>(`/torneos/${torneo.id}/bracket`, org);
  const final = despues.find((p) => p.ronda_nombre === "Final")!;
  expect([final.equipos_id_local, final.equipos_id_visitante]).toContain(perdedorEnCancha);
  await ganar(org, torneo.id, final.id, perdedorEnCancha);
  const tercero = despues.find((p) => p.ronda_nombre === "Tercer Lugar")!;
  await ganar(org, torneo.id, tercero.id, tercero.equipos_id_local!);

  // --- Cerrar desde el panel.
  await page.reload();
  const campeon = nombre(perdedorEnCancha);
  await page.getByRole("button", { name: "Cerrar Torneo" }).click();
  const modal = page.getByRole("dialog", { name: "Cerrar torneo y coronar campeones" });
  await modal.getByRole("button", { name: `Cerrar torneo y coronar a ${campeon}` }).click();
  await expect(modal).toBeHidden();
  const podio = page.locator(".podio");
  await expect(podio.locator(".podio__fila--1")).toContainText(campeon);
  await expect(page.getByText("Estado: Finalizado")).toBeVisible();

  // --- Reabrir: el podio desaparece y el torneo vuelve a Activo.
  await podio.getByRole("button", { name: "Reabrir torneo" }).click();
  await podio.getByRole("button", { name: "Reabrir torneo" }).click();
  await expect(page.locator(".podio")).toHaveCount(0);
  await expect(page.getByText("Estado: Activo")).toBeVisible();

  // --- Cerrar de nuevo: el podio se recalcula igual.
  await page.goto(`/torneo-admin/torneos/${torneo.id}/partidos`);
  await page.getByRole("button", { name: "Cerrar Torneo" }).click();
  await page.getByRole("dialog").getByRole("button", { name: `Cerrar torneo y coronar a ${campeon}` }).click();
  await expect(page.locator(".podio__fila--1")).toContainText(campeon);
});
