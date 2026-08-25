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
    if (response.status === 401 && onUnauthorized) {
      onUnauthorized();
    }
    return response;
  },
});

/** Extrae un mensaje legible del error de FastAPI ({"detail": "..."} o
 * {"detail": [{"msg": "..."}]} para 422 de validación de Pydantic). */
export function apiErrorMessage(error: unknown, fallback = "Ocurrió un error inesperado."): string {
  if (error && typeof error === "object" && "detail" in error) {
    const detail = (error as { detail: unknown }).detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
      return detail
        .map((d) => (d && typeof d === "object" && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
        .join(" ");
    }
  }
  return fallback;
}
