import { useEffect, useRef, useState, type MouseEvent } from "react";
import { NavLink, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { useAuth } from "../auth/useAuth";
import { Button } from "./ui/Button";
import { BarraDisciplinasPublica } from "./publico/BarraDisciplinasPublica";

export function NavBar() {
  const { session, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  // T2.4/D12: el estado de disciplina elegida vive en la URL de "/"
  // (`/?deporte=<slug>`), no en useState — un refresh o un link
  // compartido tienen que conservar el deporte. El NavBar se monta en
  // TODA ruta (F18), así que solo lee `?deporte=` cuando la ruta activa
  // es la home; en cualquier otra página no hay "deporte actual" que
  // resaltar.
  const deporteActual = location.pathname === "/" ? searchParams.get("deporte") : null;
  function seleccionarDeporte(slug: string | null) {
    navigate(slug ? `/?deporte=${encodeURIComponent(slug)}` : "/");
  }

  // D13: el link a Dashboard/Control de Mesa/etc. son los únicos
  // ocupantes de esta fila — con T1.1/T1.2 un anónimo no ve ninguno, y
  // `.nav-bar__links` (flex:1) dejaba un hueco expansivo vacío entre la
  // marca y "Iniciar sesión" si se renderizaba igual. Se calcula acá para
  // no renderizar el `<nav>` en absoluto cuando no hay nada adentro.
  const hayLinksDeSesion = session != null;

  // TASK-036 (UX-01): por debajo de 900px los enlaces van detrás de un botón
  // "Menú"; Usuarios, Accesos y Auditoría se agrupan en "Administración".
  // Los dos se cierran al elegir un enlace, con Escape y con un clic afuera.
  const [menuAbierto, setMenuAbierto] = useState(false);
  const [adminAbierto, setAdminAbierto] = useState(false);
  const grupoAdminRef = useRef<HTMLDivElement>(null);
  const botonAdminRef = useRef<HTMLButtonElement>(null);
  const enAdministracion = location.pathname.startsWith("/admin/");

  useEffect(() => {
    if (!adminAbierto && !menuAbierto) return;
    function alClicAfuera(e: globalThis.MouseEvent) {
      if (!(e.target instanceof Node)) return;
      if (grupoAdminRef.current && !grupoAdminRef.current.contains(e.target)) setAdminAbierto(false);
    }
    function alPresionarTecla(e: KeyboardEvent) {
      if (e.key !== "Escape") return;
      if (adminAbierto) {
        setAdminAbierto(false);
        botonAdminRef.current?.focus();
      } else {
        setMenuAbierto(false);
      }
    }
    document.addEventListener("click", alClicAfuera);
    document.addEventListener("keydown", alPresionarTecla);
    return () => {
      document.removeEventListener("click", alClicAfuera);
      document.removeEventListener("keydown", alPresionarTecla);
    };
  }, [adminAbierto, menuAbierto]);

  function alElegirEnlace(e: MouseEvent) {
    if (e.target instanceof Element && e.target.closest("a")) {
      setMenuAbierto(false);
      setAdminAbierto(false);
    }
  }

  const claseActiva = ({ isActive }: { isActive: boolean }) => (isActive ? "active" : undefined);

  return (
    <header className="nav-bar">
      <div className="nav-bar__fila1">
        <div className="nav-bar__brand">Score-App</div>
        {hayLinksDeSesion && (
          <button
            type="button"
            className="nav-bar__menu"
            aria-expanded={menuAbierto}
            aria-controls="nav-principal"
            onClick={() => setMenuAbierto((v) => !v)}
          >
            {menuAbierto ? "Cerrar menú" : "Menú"}
          </button>
        )}
        {hayLinksDeSesion && (
          // onClick por delegación: el clic real lo hace un <a>, que ya
          // funciona con teclado (Enter dispara click).
          <nav
            id="nav-principal"
            aria-label="Principal"
            className={menuAbierto ? "nav-bar__links nav-bar__links--abierto" : "nav-bar__links"}
            onClick={alElegirEnlace}
          >
            {/* portal-publico-feed-partidos-plan.md, T1.1/T1.2 (C7): el público
                anónimo ya no ve ni Dashboard ni Control de Mesa acá — el link a
                Control de Mesa quedaba visible para cualquiera aunque la ruta
                estuviera gateada por RequireRole. Dashboard se esconde para el
                anónimo (el link, no la ruta: /dashboard sigue alcanzable
                tipeada directo, ver F20 en App.routing.test.tsx) porque no
                aporta nada sin sesión. */}
            <NavLink to="/dashboard" className={claseActiva}>
              Dashboard
            </NavLink>
            {/* D6: con T1.2 mandando a un logueado siempre a /dashboard y sin
                ningún link de vuelta al portal público, nadie con sesión podía
                llegar al feed — ni el TorneoAdmin que acaba de cargar los
                partidos. TASK-040: va a /portal y no a "/", que con sesión
                redirige al dashboard. */}
            <NavLink to="/portal" className={claseActiva}>
              Portal público
            </NavLink>
            {(session?.rol === "TorneoAdmin" || session?.rol === "AdminGeneral" || session?.rol === "Arbitro") && (
              <NavLink to="/control-de-mesa" className={claseActiva}>
                Control de Mesa
              </NavLink>
            )}
            {(session?.rol === "TorneoAdmin" || session?.rol === "AdminGeneral") && (
              <NavLink to="/torneo-admin" className={claseActiva}>
                Torneo Admin
              </NavLink>
            )}
            {(session?.rol === "Arbitro" || session?.rol === "AdminGeneral") && (
              <NavLink to="/arbitro" className={claseActiva}>
                Mis partidos
              </NavLink>
            )}
            {session?.rol === "AdminGeneral" && (
              <div className="nav-bar__grupo" ref={grupoAdminRef}>
                <button
                  type="button"
                  ref={botonAdminRef}
                  className={enAdministracion ? "nav-bar__grupo-boton active" : "nav-bar__grupo-boton"}
                  aria-expanded={adminAbierto}
                  aria-controls="nav-administracion"
                  onClick={() => setAdminAbierto((v) => !v)}
                >
                  Administración <span aria-hidden="true">▾</span>
                </button>
                <div id="nav-administracion" className="nav-bar__submenu" hidden={!adminAbierto}>
                  <NavLink to="/admin/usuarios" className={claseActiva}>
                    Usuarios
                  </NavLink>
                  <NavLink to="/admin/accesos" className={claseActiva}>
                    Accesos
                  </NavLink>
                  <NavLink to="/admin/auditoria" className={claseActiva}>
                    Auditoría
                  </NavLink>
                </div>
              </div>
            )}
          </nav>
        )}
        <div className="nav-bar__session">
          {session ? (
            <>
              {/* TASK-033: el nombre lleva a "Mi cuenta" (cambio de contraseña). */}
              <NavLink to="/mi-cuenta" className="nav-bar__user" title="Mi cuenta">
                {session.username} <span className="badge">{session.rol}</span>
              </NavLink>
              <Button onClick={logout}>Salir</Button>
            </>
          ) : (
            <NavLink to="/login">Iniciar sesión</NavLink>
          )}
        </div>
      </div>
      {/* T2.3/D13: segunda fila, visible SIN sesión (el NavBar ya se
          renderiza para anónimos) — la barra misma decide si tiene algo
          que mostrar (C8: con ≤1 disciplina con contenido, no se renderiza
          nada, ni siquiera el contenedor). */}
      <BarraDisciplinasPublica deporteSeleccionado={deporteActual} onSeleccionar={seleccionarDeporte} />
    </header>
  );
}
