import { useMemo, useState } from "react";
import { apiErrorMessage } from "../../api/client";
import type { components } from "../../api/schema";
import { FiltrosRecurso } from "../../components/admin/FiltrosRecurso";
import { ResourceTable, type ResourceTableColumn } from "../../components/admin/ResourceTable";
import { LIMITE_LISTA, useResourceCrud } from "../../hooks/useResourceCrud";

// Tipado desde el contrato GENERADO del backend (ver AccesosAdmin.test.tsx
// para el mismo criterio): si AuditoriaOut gana o pierde un campo, esta
// página deja de compilar en vez de seguir asumiendo una forma vieja.
type AuditoriaRow = components["schemas"]["AuditoriaOut"];
type AccionAuditoria = AuditoriaRow["accion"];

const formatearFechaHora = (iso: string) =>
  new Date(iso).toLocaleString("es-AR", { dateStyle: "short", timeStyle: "medium" });

const ACCION_LABEL: Record<AccionAuditoria, string> = {
  crear: "Alta",
  modificar: "Modificación",
  eliminar: "Baja",
};

const ACCION_CLASE: Record<AccionAuditoria, string> = {
  crear: "auditoria-crear",
  modificar: "auditoria-modificar",
  eliminar: "auditoria-eliminar",
};

// 3A-1 (docs/plans/cierre-backlog-todos-plan.md): lista estática de las
// __tablename__ reales (backend/app/models/*.py) — no hay endpoint que las
// liste hoy, mismo criterio que el resto de catálogos estáticos de esta
// UI. A propósito el value ES el label: un autocomplete "amigable" que
// muestre un nombre distinto al que guarda AUDITORIA.Tabla no matchearía
// nada al filtrar (Fase 2 del plan, litmus de especificidad).
const TABLAS_AUDITABLES = [
  "accesos",
  "auditoria",
  "configuracion_tiempo_torneo",
  "disciplina",
  "equipo_jugador_base",
  "equipos",
  "eventos",
  "eventos_partido",
  "fase",
  "grupo",
  "grupo_equipo",
  "hitos_partido",
  "inscripciones_torneo",
  "jugador_equipo",
  "jugador_perfil_disciplina",
  "jugadores",
  "modalidad",
  "partidos",
  "sorteos",
  "torneo",
  "torneo_grupo",
  "traspasos",
  "usuarios",
];

/** Escapado RFC 4180 (EC-B): un nombre con coma o comillas
 * ("Pérez, Juan") rompe un CSV armado a mano con `join(",")` — se envuelve
 * en comillas si el campo trae coma/comilla/salto de línea, y toda comilla
 * interna se duplica. */
function celdaCsv(valor: string): string {
  if (/[",\n]/.test(valor)) {
    return `"${valor.replace(/"/g, '""')}"`;
  }
  return valor;
}

function descargarCsvAuditoria(filas: AuditoriaRow[]) {
  const encabezado = ["Fecha", "Tabla", "Registro_ID", "Accion", "Cambios", "Usuario_ID", "IP"];
  const lineas = filas.map((f) => {
    const { completo } = resumirCambios(f);
    return [
      f.fecha,
      f.tabla,
      String(f.registro_id),
      ACCION_LABEL[f.accion],
      completo,
      f.usuario_id === null ? "" : String(f.usuario_id),
      f.ip ?? "",
    ]
      .map(celdaCsv)
      .join(",");
  });
  const csv = [encabezado.join(","), ...lineas].join("\r\n");
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const enlace = document.createElement("a");
  enlace.href = url;
  enlace.download = `auditoria_${new Date().toISOString().slice(0, 19).replace(/[:T]/g, "-")}.csv`;
  document.body.appendChild(enlace);
  enlace.click();
  document.body.removeChild(enlace);
  URL.revokeObjectURL(url);
}

/** Compacta `datos_anteriores`/`datos_nuevos` en una línea legible.
 *
 * 'crear' solo trae `datos_nuevos` (no hay "antes" de qué comparar);
 * 'modificar'/'eliminar' traen los dos, con las MISMAS claves en ambos
 * (el backend solo registra lo que cambió — ver core/auditoria.py), así
 * que alcanza con recorrer una de las dos para armar el diff campo por
 * campo. El texto completo queda en el `title` para quien necesite verlo
 * entero: una fila con 8 columnas cambiadas no entra en una línea de
 * tabla, y truncarla sin dejar un lugar para ver el resto perdería el
 * dato, no solo el espacio. */
function resumirCambios(fila: AuditoriaRow): { resumen: string; completo: string } {
  if (fila.accion === "crear") {
    const entradas = Object.entries(fila.datos_nuevos ?? {});
    const resumen = entradas.map(([campo, valor]) => `${campo}: ${valor}`).join(" · ");
    return { resumen: resumen || "—", completo: resumen };
  }
  const claves = new Set([
    ...Object.keys(fila.datos_anteriores ?? {}),
    ...Object.keys(fila.datos_nuevos ?? {}),
  ]);
  const partes = [...claves].map((campo) => {
    const antes = fila.datos_anteriores?.[campo];
    const despues = fila.datos_nuevos?.[campo];
    return `${campo}: ${antes ?? "—"} → ${despues ?? "—"}`;
  });
  const resumen = partes.join(" · ");
  return { resumen: resumen || "—", completo: resumen };
}

/** Auditoría de cambios — solo AdminGeneral (el backend lo exige igual,
 * ver routes/auditoria.py). Mismo patrón que AccesosAdmin: de solo
 * lectura, sin `onSelect` ni `onSoftDelete` — una bitácora editable desde
 * la propia pantalla que audita deja de servir como evidencia.
 *
 * A diferencia de Accesos (una sola tabla, ACCESOS), acá el universo es
 * CUALQUIER entidad del sistema — por eso el filtro central es "Tabla" en
 * vez de "Resultado". */
export function AuditoriaAdminPage() {
  const [tablaFiltro, setTablaFiltro] = useState("");
  const [accionFiltro, setAccionFiltro] = useState("");
  const [registroIdFiltro, setRegistroIdFiltro] = useState("");
  const [desde, setDesde] = useState("");
  const [hasta, setHasta] = useState("");

  // 3A-2: vacío = sin filtrar (comportamiento actual); un valor no
  // numérico no manda el filtro en vez de romper el fetch — no hay botón
  // de submit acá (la lista es reactiva), así que "deshabilitar el
  // submit" se traduce en "no agregar un query param inválido".
  const registroIdNum = registroIdFiltro.trim() === "" ? null : Number(registroIdFiltro);
  const registroIdValido = registroIdNum !== null && Number.isInteger(registroIdNum) && registroIdNum > 0;

  const listParams = useMemo(() => {
    const params: Record<string, unknown> = {};
    if (tablaFiltro) params.tabla = tablaFiltro;
    if (accionFiltro) params.accion = accionFiltro;
    if (registroIdValido) params.registro_id = registroIdNum;
    if (desde) params.desde = desde;
    if (hasta) params.hasta = hasta;
    return params;
  }, [tablaFiltro, accionFiltro, registroIdValido, registroIdNum, desde, hasta]);

  const crud = useResourceCrud<AuditoriaRow>({
    resourceKey: "auditoria",
    basePath: "/api/v1/auditoria",
    listParams,
  });

  const filas = crud.listQuery.data ?? [];
  const hayFiltros = Boolean(tablaFiltro || accionFiltro || registroIdFiltro.trim() || desde || hasta);

  const columnas: ResourceTableColumn<AuditoriaRow>[] = [
    { key: "fecha", label: "Fecha y hora", render: (r) => formatearFechaHora(r.fecha) },
    { key: "tabla", label: "Entidad", render: (r) => `${r.tabla} #${r.registro_id}` },
    {
      key: "accion",
      label: "Acción",
      render: (r) => <span className={ACCION_CLASE[r.accion]}>{ACCION_LABEL[r.accion]}</span>,
    },
    {
      key: "cambios",
      label: "Cambios",
      render: (r) => {
        const { resumen, completo } = resumirCambios(r);
        return (
          <span className="auditoria-cambios" title={completo}>
            {resumen}
          </span>
        );
      },
    },
    {
      key: "usuario",
      label: "Hecho por",
      render: (r) => (r.usuario_id === null ? <span className="muted">—</span> : `#${r.usuario_id}`),
    },
    { key: "ip", label: "IP", render: (r) => r.ip ?? "—" },
  ];

  return (
    <div className="page">
      <div className="page__header">
        <h1>Auditoría</h1>
      </div>
      <p className="muted">
        Cada alta, modificación o baja de cualquier entidad del sistema, con quién la hizo y qué
        cambió. Se registra sola; no se puede editar ni borrar desde acá. Se conserva 1 mes.
      </p>

      <FiltrosRecurso
        selects={[
          {
            name: "tabla",
            label: "Tabla",
            value: tablaFiltro,
            labelTodas: "Todas",
            // 3A-1: nombres reales de __tablename__, no una versión
            // "amigable" — ver el comentario de TABLAS_AUDITABLES.
            options: TABLAS_AUDITABLES.map((t) => ({ value: t, label: t })),
            onChange: setTablaFiltro,
          },
          {
            name: "accion",
            label: "Acción",
            value: accionFiltro,
            labelTodas: "Todas",
            options: [
              { value: "crear", label: "Alta" },
              { value: "modificar", label: "Modificación" },
              { value: "eliminar", label: "Baja" },
            ],
            onChange: setAccionFiltro,
          },
        ]}
        hayFiltrosAplicados={hayFiltros}
        onLimpiar={() => {
          setTablaFiltro("");
          setAccionFiltro("");
          setRegistroIdFiltro("");
          setDesde("");
          setHasta("");
        }}
      />

      <div className="filtros-recurso">
        <label>
          ID de registro
          <input
            type="number"
            inputMode="numeric"
            min={1}
            placeholder="ej: 42"
            value={registroIdFiltro}
            onChange={(e) => setRegistroIdFiltro(e.target.value)}
          />
        </label>
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
          Mostrando los {LIMITE_LISTA} más recientes. Acotá el rango de fechas o filtrá por entidad
          para ver más atrás.
        </p>
      )}
      {crud.listQuery.isError && <p className="error-text">{apiErrorMessage(crud.listQuery.error)}</p>}

      <div className="filtros-recurso">
        <button
          type="button"
          disabled={filas.length === 0}
          onClick={() => descargarCsvAuditoria(filas)}
        >
          ⬇ Descargar CSV
        </button>
        {/* 3A-3, EC-B: si hay más filas de las que trajo la paginación, el
            CSV solo puede reflejar lo que YA está en pantalla — avisar en
            vez de exportar en silencio un archivo incompleto. */}
        {crud.truncado && filas.length > 0 && (
          <span className="muted">
            Descarga solo las primeras {LIMITE_LISTA} filas — afiná el filtro para exportar menos.
          </span>
        )}
      </div>

      <ResourceTable<AuditoriaRow>
        rows={filas}
        columns={columnas}
        isLoading={crud.listQuery.isLoading}
        isError={crud.listQuery.isError}
        emptyMessage={
          hayFiltros ? "Ningún cambio coincide con estos filtros." : "Todavía no hay cambios registrados."
        }
      />
    </div>
  );
}
