import createClient from "openapi-fetch";
import type { paths } from "./schema";

const BASE_URL = import.meta.env.VITE_API_BASE_URL as string;

export const TOKEN_STORAGE_KEY = "score-app.token";

export function getStoredToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_STORAGE_KEY);
  } catch {
    return null;
  }
}

// Callback the AuthContext registers so the API layer can react to a 401
// (token expired/inválido) without importing React state here — keeps this
// file framework-agnostic and easy to test on its own.
let onUnauthorized: (() => void) | null = null;
export function setOnUnauthorized(handler: (() => void) | null) {
  onUnauthorized = handler;
}

// Segundo callback simétrico (rbac-licencias-torneos-plan.md, §5.1): un 403
// con el header X-License-Revoked (backend/app/exceptions/handlers.py) es
// distinto de un 403 genérico de rol insuficiente — el header, no un campo
// del body, es lo que permite distinguirlos acá sin leer/clonar el stream
// de la respuesta.
let onLicenseRevoked: (() => void) | null = null;
export function setOnLicenseRevoked(handler: (() => void) | null) {
  onLicenseRevoked = handler;
}

export const api = createClient<paths>({ baseUrl: BASE_URL });

api.use({
  onRequest({ request }) {
    const token = getStoredToken();
    if (token) {
      request.headers.set("Authorization", `Bearer ${token}`);
    }
    return request;
  },
  onResponse({ response }) {
    // Chequeo de licencia PRIMERO y con `return` explícito: un 403 de
    // licencia nunca debe además evaluarse como un 401 (son mutuamente
    // excluyentes por status code, pero dejarlo explícito documenta la
    // prioridad — mismo orden que el backend, licencia por encima de
    // cualquier otro chequeo).
    if (response.status === 403 && response.headers.get("X-License-Revoked") === "true") {
      if (onLicenseRevoked) onLicenseRevoked();
      return response;
    }
    if (response.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return response;
  },
});

// Cierre de Fase Regular + Llaves + Playoffs (docs/plans/cierre-fase-
// regular-llaves-playoffs-plan.md): los códigos snake_case que lanzan los
// triggers nuevos (RAISE EXCEPTION 'codigo', sin traducir a español ahí —
// exceptions/handlers.py los pasa tal cual) — copy table de la Design
// review, "cada rechazo mapeado a texto + acción de recuperación".
// Desempate de eliminatoria: tiempo extra y penales (docs/plans/desempate-
// tiempo-extra-penales-plan.md, §11 "Copy de errores") — 9 códigos nuevos
// de fn_validar_forma_desempate/fn_validar_partido_eliminacion_desempate/
// fn_validar_torneo_modalidad (06_triggers.sql). El operador ya comía
// `llave_empatada_en_global_sin_desempate` como fallo crudo antes de este
// plan; estos ocho se agregan con el mismo criterio.
const CODIGOS_ERROR_TRADUCIDOS: Record<string, string> = {
  partido_vuelta_ida_sin_resolver: "Falta cerrar (o cancelar) el partido de ida antes de cerrar la vuelta.",
  llave_empatada_en_global_sin_desempate: "La llave está empatada en el marcador global — cargá el desempate en el partido de vuelta.",
  partido_eliminacion_empatado_sin_desempate: "El partido terminó empatado — cargá el desempate antes de finalizarlo.",
  torneo_cerrado_resultados_bloqueados: "Este torneo está cerrado — los resultados están bloqueados. Reabrilo para poder editarlos.",
  tanda_penales_empatada: "Una tanda de penales no puede terminar empatada.",
  tanda_penales_fuera_de_rango: "Marcador de tanda inválido.",
  ganador_desempate_contradice_tanda: "El ganador no coincide con el marcador de la tanda.",
  metodo_desempate_incoherente: "El método y el marcador de la tanda no coinciden.",
  desempate_sin_metodo: "Falta indicar cómo se resolvió el empate.",
  desempate_en_ida_no_permitido: "El desempate se registra en la vuelta, no en la ida.",
  penales_no_aplican_a_corrido: "Este torneo no usa penales.",
};

/** Extrae un mensaje legible del error de FastAPI ({"detail": "..."} o
 * {"detail": [{"msg": "..."}]} para 422 de validación de Pydantic). */
export function apiErrorMessage(error: unknown, fallback = "Ocurrió un error inesperado."): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return CODIGOS_ERROR_TRADUCIDOS[detail] ?? detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join(" ");
    }
  }
  return fallback;
}
