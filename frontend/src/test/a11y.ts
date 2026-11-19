import { screen, waitFor } from "@testing-library/react";
import type { UserEvent } from "@testing-library/user-event";
import axe from "axe-core";
import { expect } from "vitest";

/** TASK-044 (QA-12): falla si axe encuentra infracciones graves o críticas
 * dentro de `contenedor`.
 *
 * Reglas apagadas, porque jsdom no puede evaluarlas y darían resultados
 * falsos (las cubre la revisión en navegador real, TASK-037/042):
 * - `color-contrast`: jsdom no calcula estilos ni colores reales.
 * - `region`/`landmark-*`/`page-has-heading-one`: se prueba un pedazo de
 *   la app, no la página entera con su `<main>` y su barra.
 */
export async function esperarSinInfracciones(contenedor: Element = document.body) {
  const resultado = await axe.run(contenedor, {
    runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "best-practice"] },
    rules: {
      "color-contrast": { enabled: false },
      region: { enabled: false },
      "landmark-one-main": { enabled: false },
      "landmark-unique": { enabled: false },
      "page-has-heading-one": { enabled: false },
    },
  });
  const graves = resultado.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
  const detalle = graves.map(
    (v) =>
      `${v.id} (${v.impact}): ${v.help}\n` +
      v.nodes
        .slice(0, 3)
        .map((n) => `    ${n.target.join(" ")}`)
        .join("\n"),
  );
  expect(detalle, "infracciones de accesibilidad graves o críticas").toEqual([]);
}

/** TASK-044: recorrido de teclado de un modal, el mismo para los nueve.
 *
 * Abre con `disparador`, y comprueba: el foco entra al diálogo, no hay
 * infracciones graves, Tab no se escapa, Escape cierra y el foco vuelve al
 * botón que lo abrió (TASK-035). El modal tiene que abrirse sin datos
 * cargados, si no Escape pregunta antes de descartar. */
export async function comprobarModalAccesible(user: UserEvent, disparador: HTMLElement) {
  await user.click(disparador);
  const dialogo = await screen.findByRole("dialog");
  await waitFor(() => expect(dialogo.contains(document.activeElement)).toBe(true));
  expect(dialogo).toHaveAccessibleName();

  await esperarSinInfracciones();

  for (let i = 0; i < 12; i++) {
    await user.tab();
    expect(dialogo.contains(document.activeElement), `Tab #${i + 1} sacó el foco del diálogo`).toBe(true);
  }
  await user.tab({ shift: true });
  expect(dialogo.contains(document.activeElement)).toBe(true);

  await user.keyboard("{Escape}");
  await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  await waitFor(() => expect(document.activeElement).toBe(disparador));
}
