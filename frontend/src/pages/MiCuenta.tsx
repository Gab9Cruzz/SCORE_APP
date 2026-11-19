import { useState, type FormEvent } from "react";
import { api, apiErrorMessage } from "../api/client";
import { useAuth } from "../auth/useAuth";

/** Mínimo del backend (app/core/politica_password.py). Se repite acá solo
 * para avisar antes de enviar; quien decide es el backend. */
const LARGO_MINIMO = 10;

/** "Mi cuenta" (TASK-033, FUN-13/UX-15): cualquier usuario con sesión cambia
 * su contraseña. Cambiarla cierra las demás sesiones; esta sigue abierta con
 * el token nuevo que devuelve el backend. */
export function MiCuentaPage() {
  const { session, reemplazarToken } = useAuth();
  const [actual, setActual] = useState("");
  const [nueva, setNueva] = useState("");
  const [confirmacion, setConfirmacion] = useState("");
  const [enviando, setEnviando] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [listo, setListo] = useState(false);

  const errorLocal =
    nueva !== "" && nueva.length < LARGO_MINIMO
      ? `La contraseña nueva debe tener al menos ${LARGO_MINIMO} caracteres.`
      : confirmacion !== "" && confirmacion !== nueva
        ? "La confirmación no coincide con la contraseña nueva."
        : null;
  const puedeEnviar = actual !== "" && nueva.length >= LARGO_MINIMO && confirmacion === nueva && !enviando;

  async function enviar(e: FormEvent) {
    e.preventDefault();
    if (!puedeEnviar) return;
    setEnviando(true);
    setError(null);
    setListo(false);
    try {
      const { data, error: err } = await api.POST("/api/v1/auth/cambiar-password", {
        body: { password_actual: actual, password_nueva: nueva },
      });
      if (err) throw err;
      reemplazarToken(data.access_token);
      setActual("");
      setNueva("");
      setConfirmacion("");
      setListo(true);
    } catch (e) {
      setError(apiErrorMessage(e, "No se pudo cambiar la contraseña."));
    } finally {
      setEnviando(false);
    }
  }

  return (
    <div className="page">
      <h1>Mi cuenta</h1>
      {session && (
        <p className="muted">
          {session.username} · <span className="badge">{session.rol}</span>
        </p>
      )}

      <h2>Cambiar contraseña</h2>
      <p className="muted">Al cambiarla se cierran tus sesiones abiertas en otros dispositivos.</p>
      <form className="resource-form" onSubmit={enviar} noValidate>
        <label>
          Contraseña actual
          <input
            type="password"
            autoComplete="current-password"
            value={actual}
            onChange={(e) => setActual(e.target.value)}
            required
          />
        </label>
        <label>
          Contraseña nueva
          <input
            type="password"
            autoComplete="new-password"
            value={nueva}
            onChange={(e) => setNueva(e.target.value)}
            minLength={LARGO_MINIMO}
            required
          />
        </label>
        <label>
          Repetir contraseña nueva
          <input
            type="password"
            autoComplete="new-password"
            value={confirmacion}
            onChange={(e) => setConfirmacion(e.target.value)}
            required
          />
        </label>
        {errorLocal && <p className="muted">{errorLocal}</p>}
        {error && (
          <p className="error-text" role="alert">
            {error}
          </p>
        )}
        {listo && <p role="status">Contraseña actualizada. Las demás sesiones se cerraron.</p>}
        <div className="resource-form__actions">
          <button type="submit" disabled={!puedeEnviar}>
            {enviando ? "Guardando..." : "Cambiar contraseña"}
          </button>
        </div>
      </form>
    </div>
  );
}
