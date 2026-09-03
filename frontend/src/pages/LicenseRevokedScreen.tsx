/** Pantalla de bloqueo por licencia revocada (rbac-licencias-torneos-plan.md,
 * §5.2) — clon del patrón de `LoginPrompt` (`pages/Login.tsx`): nunca un
 * error crudo, una pantalla completa explicando qué pasó. `App.tsx` la
 * muestra en vez del shell normal cuando `AuthContext.licenseRevoked` es
 * true, sin importar en qué ruta estaba el usuario cuando se lo bloqueó.
 *
 * Texto exacto del spec: "Licencia Inactiva o Revocada. Contacte al
 * administrador." — no una paráfrasis. `<a href>` plano (no un Link de
 * react-router), mismo criterio que LoginPrompt: la navegación recarga la
 * página entera, lo que resetea `licenseRevoked` a su valor inicial sin
 * tener que limpiarlo a mano acá. */
export function LicenseRevokedScreen() {
  return (
    <div className="login-page">
      <div className="login-form login-form--prompt">
        <h1>Licencia Inactiva o Revocada</h1>
        <p>Contacte al administrador.</p>
        <a className="button-link" href="/login">
          Volver a iniciar sesión
        </a>
      </div>
    </div>
  );
}
