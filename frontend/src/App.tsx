import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";
import { useAuth } from "./auth/useAuth";
import { NavBar } from "./components/NavBar";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { RequireRole } from "./components/RequireRole";
import { Estado } from "./components/ui/Estado";
import { LicenseRevokedScreen } from "./pages/LicenseRevokedScreen";
import { LoginPage } from "./pages/Login";
import { NoEncontradaPage } from "./pages/NoEncontrada";
import { FeedPartidosPage } from "./pages/publico/FeedPartidos";

// TASK-041 (FE-03): cada sección se descarga cuando se visita. En el
// paquete inicial quedan solo el feed (la portada del visitante anónimo),
// el login y las páginas de error; el partido en vivo y el torneo público
// se piden al abrirlos.
const DetalleTorneoPublicoPage = lazy(() => import("./pages/publico/DetalleTorneoPublico").then((m) => ({ default: m.DetalleTorneoPublicoPage })));
const PartidoEnVivoPage = lazy(() => import("./pages/PartidoEnVivo").then((m) => ({ default: m.PartidoEnVivoPage })));
const ControlDeMesaPage = lazy(() =>
  import("./pages/control-mesa/ControlDeMesa").then((m) => ({ default: m.ControlDeMesaPage })),
);
const GestionarPartidoPage = lazy(() =>
  import("./pages/control-mesa/GestionarPartido").then((m) => ({ default: m.GestionarPartidoPage })),
);
const DashboardPage = lazy(() => import("./pages/Dashboard").then((m) => ({ default: m.DashboardPage })));
const MiCuentaPage = lazy(() => import("./pages/MiCuenta").then((m) => ({ default: m.MiCuentaPage })));
const MisPartidosPage = lazy(() => import("./pages/arbitro/MisPartidos").then((m) => ({ default: m.MisPartidosPage })));
const AccesosAdminPage = lazy(() =>
  import("./pages/admin/AccesosAdmin").then((m) => ({ default: m.AccesosAdminPage })),
);
const AuditoriaAdminPage = lazy(() =>
  import("./pages/admin/AuditoriaAdmin").then((m) => ({ default: m.AuditoriaAdminPage })),
);
const UsuariosAdminPage = lazy(() =>
  import("./pages/admin/UsuariosAdmin").then((m) => ({ default: m.UsuariosAdminPage })),
);
const CatalogoDisciplinasPage = lazy(() =>
  import("./pages/torneo-admin/CatalogoDisciplinas").then((m) => ({ default: m.CatalogoDisciplinasPage })),
);
const DetalleEquipoPage = lazy(() =>
  import("./pages/torneo-admin/DetalleEquipo").then((m) => ({ default: m.DetalleEquipoPage })),
);
const EquiposAdminPage = lazy(() =>
  import("./pages/torneo-admin/EquiposAdmin").then((m) => ({ default: m.EquiposAdminPage })),
);
const JugadoresAdminPage = lazy(() =>
  import("./pages/torneo-admin/JugadoresAdmin").then((m) => ({ default: m.JugadoresAdminPage })),
);
const PerfilJugadorAdminPage = lazy(() =>
  import("./pages/torneo-admin/PerfilJugadorAdmin").then((m) => ({ default: m.PerfilJugadorAdminPage })),
);
const RegistroLoteAdminPage = lazy(() =>
  import("./pages/torneo-admin/RegistroLoteAdmin").then((m) => ({ default: m.RegistroLoteAdminPage })),
);
const TorneoAdminLayout = lazy(() =>
  import("./pages/torneo-admin/TorneoAdminLayout").then((m) => ({ default: m.TorneoAdminLayout })),
);
const TorneosAdminPage = lazy(() =>
  import("./pages/torneo-admin/TorneosAdmin").then((m) => ({ default: m.TorneosAdminPage })),
);
const EquiposDelTorneoPage = lazy(() =>
  import("./pages/torneo-admin/torneo-dashboard/EquiposDelTorneo").then((m) => ({ default: m.EquiposDelTorneoPage })),
);
const EstadisticasDelTorneoPage = lazy(() =>
  import("./pages/torneo-admin/torneo-dashboard/EstadisticasDelTorneo").then((m) => ({
    default: m.EstadisticasDelTorneoPage,
  })),
);
const PartidosDelTorneoPage = lazy(() =>
  import("./pages/torneo-admin/torneo-dashboard/PartidosDelTorneo").then((m) => ({ default: m.PartidosDelTorneoPage })),
);
const PlantillasDelTorneoPage = lazy(() =>
  import("./pages/torneo-admin/torneo-dashboard/PlantillasDelTorneo").then((m) => ({
    default: m.PlantillasDelTorneoPage,
  })),
);
const TorneoDashboardPage = lazy(() =>
  import("./pages/torneo-admin/torneo-dashboard/TorneoDashboard").then((m) => ({ default: m.TorneoDashboardPage })),
);
const TraspasosDelTorneoPage = lazy(() =>
  import("./pages/torneo-admin/torneo-dashboard/TraspasosDelTorneo").then((m) => ({
    default: m.TraspasosDelTorneoPage,
  })),
);

export function App() {
  const { licenseRevoked, session } = useAuth();
  const { pathname } = useLocation();

  // rbac-licencias-torneos-plan.md, §5.2: chequeado ANTES que las rutas
  // normales — reemplaza el shell entero (nav incluida), sin importar en
  // qué ruta estaba el usuario cuando se le revocó la licencia. No es un
  // <Route> más: una licencia revocada corta el acceso a TODA la app, no
  // solo a las pantallas protegidas por RequireRole.
  if (licenseRevoked) {
    return <LicenseRevokedScreen />;
  }

  return (
    <div className="app-shell">
      {/* TASK-037 (UX-23): con teclado, el AdminGeneral tabulaba todo el menú
          antes de llegar a la página. Primer elemento enfocable; visible
          solo con foco. */}
      <a
        className="saltar-contenido"
        href="#contenido"
        onClick={(e) => {
          e.preventDefault();
          document.getElementById("contenido")?.focus();
        }}
      >
        Saltar al contenido
      </a>
      <NavBar />
      <main id="contenido" tabIndex={-1}>
        {/* TASK-041: un error de render en una página no tumba la app; la
            barra de navegación queda. Al cambiar de ruta se reintenta. */}
        <ErrorBoundary claveReinicio={pathname}>
          <Suspense
            fallback={
              <div className="page">
                <Estado tipo="cargando">Cargando…</Estado>
              </div>
            }
          >
            <Routes>
              {/* portal-publico-feed-partidos-plan.md, T4.1/C16: "/" decide
              por sesión — es el único cambio de esta entrega que toca a
              TODO usuario existente, así que va con su propio test
              (App.routing.test.tsx) y este comentario explicando por qué.
              Un anónimo ve el feed público (la nueva home); un usuario
              logueado sigue exactamente donde ya estaba, redirigido a
              /dashboard — el arranque de nadie con sesión cambia. */}
              <Route path="/" element={session ? <Navigate to="/dashboard" replace /> : <FeedPartidosPage />} />
              {/* TASK-040 (FUN-12): el feed para todos, con o sin sesión. El
              enlace "Portal público" apuntaba a "/", que con sesión
              redirige al dashboard: el enlace no llevaba al portal. */}
              <Route path="/portal" element={<FeedPartidosPage />} />
              <Route path="/dashboard" element={<DashboardPage />} />
              <Route path="/login" element={<LoginPage />} />
              {/* TASK-033: cualquier cuenta con sesión, sin importar el rol. */}
              <Route
                path="/mi-cuenta"
                element={
                  <RequireRole roles={["AdminGeneral", "TorneoAdmin", "Arbitro", "Publico"]}>
                    <MiCuentaPage />
                  </RequireRole>
                }
              />
              <Route
                path="/control-de-mesa"
                element={
                  <RequireRole roles={["TorneoAdmin", "AdminGeneral", "Arbitro"]}>
                    <ControlDeMesaPage />
                  </RequireRole>
                }
              />
              {/* Vista inmersiva de un partido (gestionar-partido-alineaciones-plan.md).
              Ruta propia y no un panel por useState: sin URL, el botón Atrás
              salía del módulo entero y un refresh en pleno partido devolvía al
              operador a la lista. Mismo RequireRole que /control-de-mesa — no
              se puede colgar de /partidos/:id, que es público sin auth. */}
              <Route
                path="/control-de-mesa/partido/:partidoId"
                element={
                  <RequireRole roles={["TorneoAdmin", "AdminGeneral", "Arbitro"]}>
                    <GestionarPartidoPage />
                  </RequireRole>
                }
              />
              <Route path="/partido/:partidoId/en-vivo" element={<PartidoEnVivoPage />} />
              {/* "Detalle del Partido" (control-mesa-centralizacion-fixture-
              plan.md, ítem 5) — misma página que /partido/:id/en-vivo
              (generalizada: sirve para cualquier estado, no solo "En
              curso"), nueva ruta con el nombre que usa el botón de
              PartidosDelTorneo.tsx. La ruta vieja se mantiene tal cual —
              Dashboard.tsx la linkea como "Ver en vivo →". */}
              <Route path="/partidos/:partidoId" element={<PartidoEnVivoPage />} />

              {/* Vista pública de torneo (portal-publico-feed-partidos-plan.md,
              T5.2) — pública, sin RequireRole: posiciones/resultados/
              goleadores con los endpoints de /estadisticas/* que ya eran
              públicos. Gateada por Publicado del lado del backend (C2). */}
              <Route path="/torneos/:torneoId" element={<DetalleTorneoPublicoPage />} />

              {/* Módulo Árbitro (roles-3-modulos-plan.md, Fase 3, D3 + Fase 4,
              D1): ruta única, sin layout/Outlet — hoy es una sola
              pantalla. AdminGeneral se agregó en Fase 4 (acceso cruzado
              "sin restricción" del plan original) — sin selector "entrar
              como", solo la lista de roles ampliada. En la práctica un
              AdminGeneral casi siempre ve el empty-state (no suele tener
              arbitro_id asignado), pero backend-side ya tenía acceso
              (bypass de require_roles, D3 confirmado por la voz externa). */}
              <Route
                path="/arbitro"
                element={
                  <RequireRole roles={["Arbitro", "AdminGeneral"]}>
                    <MisPartidosPage />
                  </RequireRole>
                }
              />

              {/* Módulo Admin General (roles-3-modulos-plan.md, Fase 4, D4):
              ruta standalone, NO anidada bajo /torneo-admin — ese layout
              no gatea por pestaña, así que un tab acá le mostraría un
              link muerto a TorneoAdmin. RequireRole solo AdminGeneral,
              coincide exacto con el gate literal de escritura del
              backend (usuarios.py). */}
              <Route
                path="/admin/usuarios"
                element={
                  <RequireRole roles={["AdminGeneral"]}>
                    <UsuariosAdminPage />
                  </RequireRole>
                }
              />

              {/* Bitácora de inicios de sesión — mismo gate que Usuarios y por
              la misma razón: es información de todas las cuentas del
              sistema. El backend lo exige igual (routes/accesos.py); esto
              evita que un TorneoAdmin llegue a una pantalla que solo le
              devolvería 403. */}
              <Route
                path="/admin/accesos"
                element={
                  <RequireRole roles={["AdminGeneral"]}>
                    <AccesosAdminPage />
                  </RequireRole>
                }
              />

              {/* Auditoría de cambios — mismo gate que Accesos y por la misma
              razón, pero más sensible todavía: expone alta/modificación/
              baja de CUALQUIER entidad, torneos incluidos, no solo la
              bitácora de login. */}
              <Route
                path="/admin/auditoria"
                element={
                  <RequireRole roles={["AdminGeneral"]}>
                    <AuditoriaAdminPage />
                  </RequireRole>
                }
              />

              {/* Módulo Torneo Admin (roles-3-modulos-plan.md, Fase 2, D2). El
              gate de rol vive DENTRO de TorneoAdminLayout (RequireRole
              envolviendo el <Outlet/>), no acá — así el mismo layout se
              puede usar sin repetir el gate en cada sub-ruta. */}
              <Route path="/torneo-admin" element={<TorneoAdminLayout />}>
                <Route index element={<Navigate to="torneos" replace />} />
                <Route path="torneos" element={<TorneosAdminPage />} />
                {/* Dashboard scoped de UNA edición puntual (torneos-admin-plan.md,
                Fase 2): "Ver Torneo" desde la tarjeta de arriba entra acá.
                No es una pestaña de PESTANIAS — mismo criterio que
                jugadores/:jugadorId/perfil, alcanzable solo por link, no
                por tab. */}
                <Route path="torneos/:torneoId" element={<TorneoDashboardPage />}>
                  <Route index element={<Navigate to="equipos" replace />} />
                  <Route path="equipos" element={<EquiposDelTorneoPage />} />
                  <Route path="plantillas" element={<PlantillasDelTorneoPage />} />
                  <Route path="traspasos" element={<TraspasosDelTorneoPage />} />
                  <Route path="partidos" element={<PartidosDelTorneoPage />} />
                  <Route path="estadisticas" element={<EstadisticasDelTorneoPage />} />
                </Route>
                <Route path="disciplinas" element={<CatalogoDisciplinasPage />} />
                <Route path="equipos" element={<EquiposAdminPage />} />
                {/* Detalle del Equipo (gestion-avanzada-equipos-control-mesa-
                plan.md, Flujo 1) — a donde redirige la creación de un
                equipo y la acción rápida "Registrar Jugadores" del
                listado. Alcanzable solo por link, mismo criterio que
                jugadores/:jugadorId/perfil. */}
                <Route path="equipos/:equipoId" element={<DetalleEquipoPage />} />
                <Route path="jugadores" element={<JugadoresAdminPage />} />
                <Route path="jugadores/:jugadorId/perfil" element={<PerfilJugadorAdminPage />} />
                {/* Alcanzable solo desde el modal "Agregar Equipo" o el botón
                "+ Registro por lote" del dashboard scoped (ver
                RegistroLoteAdmin.tsx) — ya no hay pestaña global de
                Plantillas desde la que se llegaba antes (Fase 3). */}
                <Route path="plantillas/lote" element={<RegistroLoteAdminPage />} />
              </Route>

              {/* TASK-036 (FE-03): una ruta inexistente muestra la 404. Antes
              caía en "/" en silencio (T1.2), y un enlace roto parecía "la
              app me sacó". "/dashboard" tipeado directo sigue alcanzable
              sin sesión (decisión F20): se le sacó el link, no el acceso. */}
              <Route path="*" element={<NoEncontradaPage />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
      </main>
    </div>
  );
}
