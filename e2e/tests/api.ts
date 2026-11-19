import { expect, type Page } from "@playwright/test";
import { ADMIN_PASSWORD, API_URL } from "./entorno";

/** Preparación de datos por la API, para que cada recorrido arranque de un
 * estado conocido sin depender de otro. Lo que el recorrido quiere probar se
 * hace en el navegador; esto solo arma el escenario. */

export const FUTBOL = 1;
export const FUTBOL_11 = 1;
/** Cinco titulares: alcanza para un partido en vivo sin convocar a 22. */
export const FUTBOL_5 = 4;

export interface Sesion {
  token: string;
  username: string;
  rol: string;
  id: number;
}

/** Sufijo único por corrida: los nombres no chocan entre recorridos ni al
 * repetir la suite sobre la misma base. */
export function unico(prefijo: string): string {
  return `${prefijo} ${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
}

async function pedir<T>(
  metodo: string,
  ruta: string,
  sesion: Sesion | null,
  cuerpo?: unknown,
  esperado = [200, 201],
): Promise<T> {
  const r = await fetch(`${API_URL}/api/v1${ruta}`, {
    method: metodo,
    headers: {
      ...(cuerpo !== undefined ? { "Content-Type": "application/json" } : {}),
      ...(sesion ? { Authorization: `Bearer ${sesion.token}` } : {}),
    },
    body: cuerpo !== undefined ? JSON.stringify(cuerpo) : undefined,
  });
  const texto = await r.text();
  expect(esperado, `${metodo} ${ruta} → ${r.status}: ${texto}`).toContain(r.status);
  return (texto ? JSON.parse(texto) : null) as T;
}

export const get = <T>(ruta: string, s: Sesion | null) => pedir<T>("GET", ruta, s);
export const post = <T>(ruta: string, s: Sesion | null, cuerpo: unknown = {}) => pedir<T>("POST", ruta, s, cuerpo);
export const patch = <T>(ruta: string, s: Sesion | null, cuerpo: unknown) => pedir<T>("PATCH", ruta, s, cuerpo);
export const put = <T>(ruta: string, s: Sesion | null, cuerpo: unknown) => pedir<T>("PUT", ruta, s, cuerpo);

export async function login(username: string, password: string): Promise<Sesion> {
  // El Admin se crea en segundo plano al arrancar la API: se reintenta un
  // rato antes de dar el login por fallido.
  for (let intento = 0; ; intento++) {
    const r = await fetch(`${API_URL}/api/v1/auth/login`, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams({ username, password }),
    });
    if (r.ok) {
      const { access_token, rol } = await r.json();
      const me = await (await fetch(`${API_URL}/api/v1/auth/me`, { headers: { Authorization: `Bearer ${access_token}` } })).json();
      return { token: access_token, username, rol, id: me.id };
    }
    if (intento >= 20) throw new Error(`login ${username}: ${r.status} ${await r.text()}`);
    await new Promise((res) => setTimeout(res, 500));
  }
}

export const loginAdmin = () => login("admin", ADMIN_PASSWORD);

/** Cuenta nueva con ese rol (la crea el AdminGeneral). */
export async function crearCuenta(admin: Sesion, rol: string, prefijo: string): Promise<Sesion & { password: string }> {
  const username = `${prefijo}${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`.toLowerCase().slice(0, 40);
  const password = "e2e-clave-segura-123";
  await post("/usuarios", admin, { username, nombre: `E2E ${rol}`, password, rol });
  return { ...(await login(username, password)), password };
}

/** Abre el navegador ya con sesión (sin pasar por el formulario de login,
 * que se prueba aparte en el recorrido de roles). */
export async function conSesion(page: Page, s: Sesion) {
  await page.addInitScript(
    ([token, sesion]) => {
      localStorage.setItem("score-app.token", token);
      localStorage.setItem("score-app.session", sesion);
    },
    [s.token, JSON.stringify({ username: s.username, rol: s.rol, id: s.id })] as const,
  );
}

export async function crearEquipos(
  s: Sesion,
  nombres: string[],
  modalidadId = FUTBOL_11,
): Promise<{ id: number; nombre: string }[]> {
  const out = [];
  for (const nombre of nombres) {
    out.push(await post<{ id: number; nombre: string }>("/equipos", s, { nombre, disciplina_id: FUTBOL, modalidad_id: modalidadId }));
  }
  return out;
}

export interface Torneo {
  id: number;
  torneo_grupo_id: number;
}

export async function crearTorneo(
  s: Sesion,
  nombre: string,
  formato: "Liga" | "Eliminacion",
  extra: object = {},
  modalidadId = FUTBOL_11,
) {
  return post<Torneo>("/torneos", s, {
    torneo_grupo_nombre: nombre,
    disciplina_id: FUTBOL,
    modalidad_id: modalidadId,
    fecha_inicio: "2026-04-01",
    fecha_fin: "2026-12-31",
    formato,
    ...extra,
  });
}

/** Inscribe los equipos y devuelve el id de cada inscripción. */
export async function inscribir(s: Sesion, torneoId: number, equipoIds: number[]): Promise<number[]> {
  const out = [];
  for (const equipo_id of equipoIds) {
    out.push((await post<{ id: number }>("/inscripciones", s, { torneo_id: torneoId, equipo_id })).id);
  }
  return out;
}

/** Plantilla de una inscripción por el registro por lote (el mismo camino
 * que la pantalla de Registro por lote). */
export async function cargarPlantilla(s: Sesion, inscripcionId: number, prefijo: string, cantidad: number) {
  const marca = `${Date.now().toString(36)}${Math.floor(Math.random() * 1e4)}`;
  const filas = Array.from({ length: cantidad }, (_, i) => ({
    cedula: `E2E${marca}${i}`.slice(0, 20),
    nombre: `${prefijo} ${i + 1}`,
    correo_electronico: `e2e.${marca}.${i}@example.com`,
    dorsal: i + 1,
  }));
  const r = await post<{ insertados: { id: number; jugador_perfil_id: number }[]; rechazados: unknown[] }>(
    "/plantillas/lote/confirmar",
    s,
    { inscripcion_torneo_id: inscripcionId, fecha_inicio: "2026-01-01", filas },
  );
  expect(r.rechazados, "filas rechazadas en el lote").toEqual([]);
  return r.insertados;
}

export interface Partido {
  id: number;
  estado: string;
  equipos_id_local: number | null;
  equipos_id_visitante: number | null;
  jornada: number | null;
}

export const partidosDe = (s: Sesion, torneoId: number) => get<Partido[]>(`/partidos?torneo_id=${torneoId}&limit=200`, s);

let idEventoGol: number | null = null;

/** Cierra un partido 1-0 por la API (resultado directo): un gol del primer
 * jugador de la plantilla del ganador en ese torneo. */
export async function ganar(s: Sesion, torneoId: number, partidoId: number, ganadorId: number) {
  if (idEventoGol == null) {
    const eventos = await get<{ id: number; nombre: string }[]>("/eventos", s);
    idEventoGol = eventos.find((e) => e.nombre === "Gol")!.id;
  }
  const plantilla = await get<{ jugador_id: number }[]>(
    `/estadisticas/equipos/${ganadorId}/plantilla?torneo_id=${torneoId}`,
    s,
  );
  expect(plantilla.length, `el equipo ${ganadorId} no tiene plantilla`).toBeGreaterThan(0);
  await post(`/partidos/${partidoId}/resultado-directo`, s, {
    eventos: [{ jugador_id: plantilla[0].jugador_id, equipo_id: ganadorId, eventos_id: idEventoGol, minuto: 10 }],
  });
}
