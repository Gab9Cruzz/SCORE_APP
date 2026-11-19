// TASK-042: apertura/cierre de modales con teclado.
import { chromium } from "playwright-core";
const API = "http://127.0.0.1:8000/api/v1";
async function token(username, password) {
  const r = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({ username, password }),
  });
  return (await r.json()).access_token;
}
const CASOS = [
  ["organizador", "demo-clave-organizador", "TorneoAdmin", "torneo-admin/torneos/1/equipos", "+ Agregar Equipo"],
  ["organizador", "demo-clave-organizador", "TorneoAdmin", "torneo-admin/torneos/1/plantillas", "Gestionar plantilla"],
  ["organizador", "demo-clave-organizador", "TorneoAdmin", "control-de-mesa/partido/5", "Cargar resultado directo"],
  ["admin", "demo-admin-clave-1", "AdminGeneral", "admin/usuarios", "+ Nuevo"],
];
const browser = await chromium.launch({ executablePath: "C:/Program Files/Google/Chrome/Application/chrome.exe" });
for (const [u, p, rol, ruta, boton] of CASOS) {
  const t = await token(u, p);
  const ctx = await browser.newContext({ viewport: { width: 1280, height: 800 } });
  await ctx.addInitScript(([t, s]) => {
    localStorage.setItem("score-app.token", t);
    localStorage.setItem("score-app.session", JSON.stringify(s));
  }, [t, { username: u, rol, id: 1 }]);
  const page = await ctx.newPage();
  await page.goto("http://127.0.0.1:5173/" + ruta, { waitUntil: "networkidle" });
  const b = page.getByRole("button", { name: boton }).first();
  if (!(await b.count())) {
    console.log(`${ruta}: no hay botón "${boton}"`);
    await ctx.close();
    continue;
  }
  await b.focus();
  await page.keyboard.press("Enter");
  await page.waitForTimeout(400);
  const abierto = await page.evaluate(() => {
    const d = document.querySelector("[role=dialog], dialog[open], .modal");
    const a = document.activeElement;
    return {
      dialogo: d ? (d.getAttribute("role") || d.tagName.toLowerCase()) + (d.getAttribute("aria-modal") ? " aria-modal" : "") + (d.getAttribute("aria-labelledby") || d.getAttribute("aria-label") ? " con-nombre" : " SIN-NOMBRE") : null,
      focoDentro: !!(d && a && d.contains(a)),
      foco: a ? `${a.tagName.toLowerCase()}:"${(a.textContent || a.getAttribute("aria-label") || "").trim().slice(0, 20)}"` : null,
    };
  });
  // ¿El Tab queda atrapado en el modal?
  let escapa = false;
  for (let i = 0; i < 25; i++) {
    await page.keyboard.press("Tab");
    const dentro = await page.evaluate(() => {
      const d = document.querySelector("[role=dialog], dialog[open], .modal");
      return !d || d.contains(document.activeElement);
    });
    if (!dentro) { escapa = true; break; }
  }
  await page.keyboard.press("Escape");
  await page.waitForTimeout(300);
  const cerrado = await page.evaluate(() => {
    const a = document.activeElement;
    return {
      sigueAbierto: !!document.querySelector("[role=dialog], dialog[open], .modal"),
      focoVuelve: a ? `${a.tagName.toLowerCase()}:"${(a.textContent || "").trim().slice(0, 20)}"` : null,
    };
  });
  console.log(`${ruta} [${boton}]`, JSON.stringify({ ...abierto, tabEscapa: escapa, ...cerrado }));
  await ctx.close();
}
await browser.close();
