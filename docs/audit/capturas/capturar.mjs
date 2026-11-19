// TASK-042: capturas + métricas objetivas por pantalla y tamaño.
// Uso: node capturar.mjs <carpeta_salida>
import { chromium } from "playwright-core";
import fs from "node:fs";
import path from "node:path";

const SALIDA = process.argv[2];
const WEB = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api/v1";
const CHROME = "C:/Program Files/Google/Chrome/Application/chrome.exe";

const TAMANOS = [
  { nombre: "360", width: 360, height: 740 },
  { nombre: "768", width: 768, height: 1024 },
  { nombre: "1280", width: 1280, height: 800 },
  { nombre: "1920", width: 1920, height: 1080 },
];

const CUENTAS = {
  admin: { username: "admin", password: "demo-admin-clave-1" },
  organizador: { username: "organizador", password: "demo-clave-organizador" },
  arbitro: { username: "arbitro1", password: "demo-clave-arbitro1" },
};

const PANTALLAS = [
  ["anonimo", "feed", "/"],
  ["anonimo", "detalle-torneo", "/torneos/5"],
  ["anonimo", "partido-en-vivo", "/partidos/5"],
  ["anonimo", "login", "/login"],
  ["organizador", "dashboard", "/dashboard"],
  ["organizador", "control-mesa", "/control-de-mesa"],
  ["organizador", "gestionar-partido", "/control-de-mesa/partido/5"],
  ["organizador", "torneos", "/torneo-admin/torneos"],
  ["organizador", "torneo-equipos", "/torneo-admin/torneos/1/equipos"],
  ["organizador", "torneo-plantillas", "/torneo-admin/torneos/1/plantillas"],
  ["organizador", "torneo-traspasos", "/torneo-admin/torneos/1/traspasos"],
  ["organizador", "torneo-partidos", "/torneo-admin/torneos/1/partidos"],
  ["organizador", "torneo-estadisticas", "/torneo-admin/torneos/1/estadisticas"],
  ["organizador", "equipos", "/torneo-admin/equipos"],
  ["organizador", "detalle-equipo", "/torneo-admin/equipos/1"],
  ["organizador", "jugadores", "/torneo-admin/jugadores"],
  ["organizador", "registro-lote", "/torneo-admin/plantillas/lote"],
  ["arbitro", "mis-partidos", "/arbitro"],
  ["admin", "usuarios", "/admin/usuarios"],
  ["admin", "accesos", "/admin/accesos"],
  ["admin", "auditoria", "/admin/auditoria"],
  ["admin", "mi-cuenta", "/mi-cuenta"],
];

async function sesion(rol) {
  if (rol === "anonimo") return null;
  const c = CUENTAS[rol];
  const r = await fetch(`${API}/auth/login`, {
    method: "POST",
    headers: { "Content-Type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams(c),
  });
  const { access_token, rol: rolReal } = await r.json();
  const me = await (await fetch(`${API}/auth/me`, { headers: { Authorization: `Bearer ${access_token}` } })).json();
  return { token: access_token, session: { username: c.username, rol: rolReal, id: me.id } };
}

/** Métricas que no dependen de mirar la imagen. */
function medir() {
  const vw = window.innerWidth;
  const doc = document.documentElement;
  const desbordan = [];
  for (const el of document.querySelectorAll("body *")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.right > vw + 1) {
      // Solo el elemento más externo que desborda, no todos sus hijos.
      const padre = el.parentElement?.getBoundingClientRect();
      if (padre && padre.right > vw + 1) continue;
      const cls = typeof el.className === "string" ? el.className.split(" ")[0] : "";
      desbordan.push(`${el.tagName.toLowerCase()}${cls ? "." + cls : ""} (${Math.round(r.right - vw)}px)`);
    }
  }
  const chicos = [];
  for (const el of document.querySelectorAll("button, a, input, select, [role=button], [role=tab]")) {
    const r = el.getBoundingClientRect();
    if (r.width === 0 || r.height === 0) continue;
    if (r.height < 32 || r.width < 32) {
      const txt = (el.textContent || el.getAttribute("aria-label") || el.getAttribute("type") || "").trim().slice(0, 24);
      chicos.push(`${el.tagName.toLowerCase()} "${txt}" ${Math.round(r.width)}x${Math.round(r.height)}`);
    }
  }
  const sinNombre = [];
  for (const el of document.querySelectorAll("button, a[href], input:not([type=hidden]), select")) {
    const nombre =
      el.getAttribute("aria-label") ||
      el.textContent?.trim() ||
      (el.id && document.querySelector(`label[for="${el.id}"]`)) ||
      el.closest("label") ||
      el.getAttribute("title") ||
      el.getAttribute("placeholder");
    if (!nombre) sinNombre.push(el.outerHTML.slice(0, 80));
  }
  return {
    scrollHorizontal: doc.scrollWidth > vw + 1 ? doc.scrollWidth - vw : 0,
    alto: doc.scrollHeight,
    desbordan: desbordan.slice(0, 8),
    tactilesChicos: chicos.length,
    ejemplosChicos: chicos.slice(0, 6),
    sinNombreAccesible: sinNombre.slice(0, 5),
    h1: document.querySelector("h1")?.textContent?.trim() ?? null,
    textoCargando: /Cargando/.test(document.body.innerText),
    textoError: [...document.querySelectorAll(".error-text")].map((e) => e.textContent.trim()).slice(0, 3),
  };
}

/** Orden de tabulación: los primeros N focos y si el foco se ve. */
async function teclado(page, n = 12) {
  const pasos = [];
  await page.mouse.click(1, 1);
  for (let i = 0; i < n; i++) {
    await page.keyboard.press("Tab");
    pasos.push(
      await page.evaluate(() => {
        const el = document.activeElement;
        if (!el || el === document.body) return null;
        const cs = getComputedStyle(el);
        const visible =
          (cs.outlineStyle !== "none" && parseFloat(cs.outlineWidth) > 0) || cs.boxShadow !== "none";
        const txt = (el.textContent || el.getAttribute("aria-label") || el.getAttribute("name") || "").trim().slice(0, 20);
        return `${el.tagName.toLowerCase()}:"${txt}"${visible ? "" : " [SIN FOCO VISIBLE]"}`;
      }),
    );
  }
  return pasos;
}

const browser = await chromium.launch({ executablePath: CHROME, headless: true });
const informe = {};
fs.mkdirSync(SALIDA, { recursive: true });

for (const [rol, nombre, ruta] of PANTALLAS) {
  const s = await sesion(rol);
  for (const t of TAMANOS) {
    const ctx = await browser.newContext({ viewport: { width: t.width, height: t.height }, locale: "es-EC" });
    if (s) {
      await ctx.addInitScript(([token, session]) => {
        localStorage.setItem("score-app.token", token);
        localStorage.setItem("score-app.session", JSON.stringify(session));
      }, [s.token, s.session]);
    }
    const page = await ctx.newPage();
    const consola = [];
    page.on("console", (m) => m.type() === "error" && consola.push(m.text().slice(0, 160)));
    page.on("pageerror", (e) => consola.push("pageerror: " + e.message.slice(0, 160)));
    await page.goto(WEB + ruta, { waitUntil: "networkidle" });
    await page.waitForTimeout(400);
    const archivo = `${nombre}__${t.nombre}.jpg`;
    await page.screenshot({ path: path.join(SALIDA, archivo), fullPage: true, type: "jpeg", quality: 55 });
    const m = await page.evaluate(medir);
    m.consola = consola.slice(0, 5);
    if (t.nombre === "1280") m.teclado = await teclado(page);
    informe[`${nombre}__${t.nombre}`] = { rol, ruta, ...m };
    await ctx.close();
  }
  process.stdout.write(`${nombre} `);
}

await browser.close();
fs.writeFileSync(path.join(SALIDA, "..", "metricas.json"), JSON.stringify(informe, null, 2));
console.log("\nlisto");
