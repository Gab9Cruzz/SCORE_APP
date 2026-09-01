import { useMemo, useState } from "react";
import { apiErrorMessage } from "../../api/client";
import { FiltrosRecurso } from "../../components/admin/FiltrosRecurso";
import { ResourceTable, type ResourceTableColumn } from "../../components/admin/ResourceTable";
import { LIMITE_LISTA, useResourceCrud } from "../../hooks/useResourceCrud";

interface AccesoRow {
  id: number;
  usuario_id: number | null;
  username: string;
  exitoso: boolean;
  motivo: "credenciales" | "inactivo" | "bloqueado" | null;
  ip: string | null;
  user_agent: string | null;
  fecha: string;
}

const formatearFechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "medium" });

/** El motivo crudo de la base es un código corto ('credenciales',
 * 'inactivo', 'bloqueado'); acá se traduce a algo que se lee. Los tres
 * textos dicen cosas distintas a propósito: quien audita necesita separar
 * "alguien está probando contraseñas" de "una cuenta dada de baja sigue
 * intentando entrar con las suyas, que son correctas" de "el rate limit
 * de 3B-14 ya lo frenó, ni se llegó a verificar la contraseña". */
const MOTIVO: Record<string, string> = {
  credenciales: "Usuario o contraseña incorrectos",
  inactivo: "Cuenta inactiva",
  bloqueado: "Bloqueado por intentos fallidos (rate limit)",
};

/** Navegador y sistema, sacados del User-Agent. No es identificación: es
 * para que una fila diga "Chrome en Windows" en vez de 180 caracteres
 * ilegibles. El string completo queda en el `title` para quien lo
 * necesite de verdad. */
function resumirUserAgent(ua: string | null): string {
  if (!ua) return "—";
  const navegador =
    /Edg\//.test(ua) ? "Edge"
    : /OPR\//.test(ua) ? "Opera"
    : /Chrome\//.test(ua) ? "Chrome"
    : /Firefox\//.test(ua) ? "Firefox"
    : /Safari\//.test(ua) ? "Safari"
    : null;
  const sistema =
    /Windows/.test(ua) ? "Windows"
    : /Android/.test(ua) ? "Android"
    : /iPhone|iPad/.test(ua) ? "iOS"
    : /Mac OS X/.test(ua) ? "macOS"
    : /Linux/.test(ua) ? "Linux"
    : null;
  if (!navegador && !sistema) return ua.slice(0, 30);
  return [navegador, sistema].filter(Boolean).join(" · ");
}

/** Bitácora de inicios de sesión — solo AdminGeneral (el backend lo exige
 * igual, ver routes/accesos.py).
 *
 * Es de solo lectura por diseño: no hay editar ni dar de baja, ni siquiera
 * para AdminGeneral. Una bitácora que se puede corregir desde la pantalla
 * deja de ser evidencia de nada, y por eso `ResourceTable` va acá sin
 * `onSelect` ni `onSoftDelete`.
 *
 * El filtro por defecto es "solo fallidos": entrar a esta pantalla es casi
 * siempre por sospecha, no por curiosidad. Los exitosos están a un click
 * de distancia. */
export function AccesosAdminPage() {
  const [exitosoFiltro, setExitosoFiltro] = useState("false");
  const [busqueda, setBusqueda] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");

  // Todo server-side: la búsqueda por username también, a diferencia de
  // otras grillas. Acá filtrar en memoria sería inútil — lo que se busca
  // (un intento puntual) puede estar en la fila 5.000, mucho más allá del
  // techo de la primera página.
  const listParams = useMemo(() => {
    const params: Record<string, unknown> = {};
    if (exitosoFiltro) params.exitoso = exitosoFiltro === "true";
    if (busqueda.trim()) params.username = busqueda.trim();
    if (desde) params.desde = desde;
    if (hasta) params.hasta = hasta;
    return params;
  }, [exitosoFiltro, busqueda, desde, hasta]);

  const crud = useResourceCrud<AccesoRow>({
    resourceKey: "accesos",
    basePath: "/api/v1/accesos",
    listParams,
  });

  const filas = crud.listQuery.data ?? [];
  const hayFiltros = Boolean(exitosoFiltro || busqueda.trim() || desde || hasta);

  const columnas: ResourceTableColumn<AccesoRow>[] = [
    { key: "fecha", label: "Fecha y hora", render: (r) => formatearFechaHora(r.fecha) },
    { key: "username", label: "Usuario" },
    {
      key: "resultado",
      label: "Resultado",
      render: (r) =>
        r.exitoso ? (
          <span className="acceso-ok">Entró</span>
        ) : (
          <span className="acceso-fallo">{MOTIVO[r.motivo ?? ""] ?? "Falló"}</span>
        ),
    },
    {
      key: "cuenta",
      label: "Cuenta",
      // La distinción que más importa de un vistazo: un intento contra un
      // username que NO existe se ve distinto de uno contra una cuenta real.
      render: (r) =>
        r.usuario_id === null ? <span className="muted">no existe</span> : `#${r.usuario_id}`,
    },
    { key: "ip", label: "IP", render: (r) => r.ip ?? "—" },
    {
      key: "user_agent",
      label: "Desde",
      render: (r) => <span title={r.user_agent ?? ""}>{resumirUserAgent(r.user_agent)}</span>,
    },
  ];

  return (
    <div className="page">
      <div className="page__header">
        <h1>Accesos</h1>
      </div>
      <p className="muted">
        Todo intento de inicio de sesión, exitoso o fallido. Se registra solo; no se puede editar ni
        borrar desde acá.
      </p>

      <FiltrosRecurso
        selects={[
          {
            name: "exitoso",
            label: "Resultado",
            value: exitosoFiltro,
            labelTodas: "Todos",
            options: [
              { value: "false", label: "Solo fallidos" },
              { value: "true", label: "Solo exitosos" },
            ],
            onChange: setExitosoFiltro,
          },
        ]}
        busqueda={{
          value: busqueda,
          label: "Buscar usuario",
          placeholder: "Buscar por usuario...",
          onChange: setBusqueda,
        }}
        hayFiltrosAplicados={hayFiltros}
        onLimpiar={() => {
          setExitosoFiltro("");
          setBusqueda("");
          setDesde("");
          setHasta("");
        }}
      />

      <div className="filtros-recurso">
        <label>
          Desde
          <input type="date" value={desde} onChange={(e) => setDesde(e.target.value)} />
        </label>
        <label>
          Hasta
          <input type="date" value={hasta} onChange={(e) => setHasta(e.target.value)} />
        </label>
      </div>

      {crud.truncado && (
        <p className="muted">
          Mostrando los {LIMITE_LISTA} más recientes. Acotá el rango de fechas para ver más atrás.
        </p>
      )}
      {crud.listQuery.isError && <p className="error-text">{apiErrorMessage(crud.listQuery.error)}</p>}

      <ResourceTable<AccesoRow>
        rows={filas}
        columns={columnas}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage={
          hayFiltros
            ? "Ningún acceso coincide con estos filtros."
            : "Todavía no hay accesos registrados."
        }
      />
    </div>
  );
}
