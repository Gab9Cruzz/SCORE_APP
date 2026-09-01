import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import type { Equipo as EquipoRow } from "../../api/types";
import { api, apiErrorMessage } from "../../api/client";
import { useResourceCrud } from "../../hooks/useResourceCrud";

/** Contexto que llega desde el modal "Agregar Equipo" (torneos-admin-plan.md,
 * Fase 2, journey paso 5): el torneo/equipo ya se resolvieron ahí (se creó
 * el equipo y su inscripción antes de llegar acá), así que este formulario
 * no vuelve a pedirlos — la fecha de inicio se asume "hoy", sin pedirla
 * tampoco (fricción cero). Sin este state (navegación directa a
 * /torneo-admin/plantillas/lote, como hoy) el formulario se comporta
 * exactamente igual que antes. */
export interface RegistroLotePreResuelto {
  inscripcionTorneoId: number;
  /** Texto para mostrar en vez del selector — ej. "Halcones FC — Liga Relámpago Ed. 2". */
  contexto: string;
  /** A dónde vuelven los botones "Cancelar"/"Volver" — el dashboard del
   * torneo en vez de la pestaña global de Plantillas. */
  volverA: string;
}

/** A mitad de camino entre el pre-resuelto de arriba y el formulario
 * totalmente libre (Fase 3: consolidación — sin pestaña global de
 * Plantillas, el botón "+ Registro por lote" del dashboard todavía
 * necesita dejar elegir CUÁL equipo de este torneo, pero no tiene sentido
 * ofrecer el sistema entero de vuelta). El selector "Torneo — Equipo" se
 * reduce a solo "Equipo", ya filtrado a las inscripciones de este torneo. */
export interface RegistroLoteAlcanceTorneo {
  torneoId: number;
  volverA: string;
}

function esPreResuelto(v: unknown): v is RegistroLotePreResuelto {
  return !!v && typeof v === "object" && "inscripcionTorneoId" in v;
}
function esAlcanceTorneo(v: unknown): v is RegistroLoteAlcanceTorneo {
  return !!v && typeof v === "object" && "torneoId" in v && !("inscripcionTorneoId" in v);
}

interface Fila {
  cedula: string;
  nombre: string;
  correo_electronico: string;
  dorsal: string; // input crudo, se parsea a number|null al mandar
}
interface FilaValida {
  fila_index: number;
  cedula: string;
  nombre: string;
  correo_electronico: string;
  dorsal: number | null;
  jugador_id: number | null;
}
interface FilaInvalida {
  fila_index: number;
  cedula: string;
  nombre: string;
  motivo: string;
}
interface TorneoRow {
  id: number;
  nombre: string;
}
interface InscripcionRow {
  id: number;
  torneo_id: number;
  equipo_id: number;
}

const FILA_VACIA: Fila = { cedula: "", nombre: "", correo_electronico: "", dorsal: "" };

type Modo =
  | { tipo: "formulario" }
  | { tipo: "revision"; validos: FilaValida[]; invalidos: FilaInvalida[] }
  | { tipo: "resultado"; insertados: number; rechazados: FilaInvalida[] };

function filasParaEnvio(filas: Fila[]) {
  return filas
    .filter((f) => f.cedula.trim() !== "" || f.nombre.trim() !== "")
    .map((f) => ({
      cedula: f.cedula.trim(),
      nombre: f.nombre.trim(),
      correo_electronico: f.correo_electronico.trim(),
      dorsal: f.dorsal.trim() === "" ? null : Number(f.dorsal),
    }));
}

/** Registro por lote con pantalla dividida (equipos-jugadores-plan.md,
 * Fase 2, Etapa B). No usa ResourceForm (las filas son una tabla propia,
 * no un form de un solo objeto) ni useResourceCrud para las mutaciones
 * (POST /validar y /confirmar no son un create/update de un recurso —
 * devuelven 200 siempre con resultados mixtos, no un objeto creado). */
export function RegistroLoteAdminPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const preResuelto = esPreResuelto(location.state) ? location.state : null;
  const alcanceTorneo = esAlcanceTorneo(location.state) ? location.state : null;

  const [modo, setModo] = useState<Modo>({ tipo: "formulario" });
  const [filas, setFilas] = useState<Fila[]>([{ ...FILA_VACIA }]);
  const [inscripcionTorneoId, setInscripcionTorneoId] = useState<number | null>(
    preResuelto?.inscripcionTorneoId ?? null,
  );
  const [fechaInicio, setFechaInicio] = useState(preResuelto ? new Date().toISOString().slice(0, 10) : "");

  const volverDestino = preResuelto?.volverA ?? alcanceTorneo?.volverA ?? "/torneo-admin/torneos";
  const volverLabel = preResuelto || alcanceTorneo ? "Volver al Torneo" : "Volver a Plantillas";

  // Sin esto, entrar acá desde el modal "Agregar Equipo" (o desde el
  // dashboard scoped, alcanceTorneo) seguía disparando GETs sin filtrar
  // que este modo ya no usa para nada — el selector que los necesitaba no
  // se renderiza, o se renderiza ya acotado (ver abajo).
  const equipos = useResourceCrud<EquipoRow>({
    resourceKey: "equipos",
    basePath: "/api/v1/equipos",
    enabled: !preResuelto,
  });
  const torneos = useResourceCrud<TorneoRow>({
    resourceKey: "torneos",
    basePath: "/api/v1/torneos",
    enabled: !preResuelto && !alcanceTorneo,
  });
  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: alcanceTorneo ? { torneo_id: alcanceTorneo.torneoId } : undefined,
    enabled: !preResuelto,
  });

  const nombreEquipo = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );
  const nombreTorneo = useMemo(
    () => new Map((torneos.listQuery.data ?? []).map((t) => [t.id, t.nombre])),
    [torneos.listQuery.data],
  );
  function etiquetaInscripcion(i: InscripcionRow): string {
    // alcanceTorneo: el torneo ya se sabe (viene en el contexto de la
    // sub-pestaña Plantillas del dashboard), repetirlo en cada opción del
    // selector es ruido.
    if (alcanceTorneo) return nombreEquipo.get(i.equipo_id) ?? `Equipo #${i.equipo_id}`;
    return `${nombreTorneo.get(i.torneo_id) ?? `Torneo #${i.torneo_id}`} — ${nombreEquipo.get(i.equipo_id) ?? `Equipo #${i.equipo_id}`}`;
  }

  const validarMutation = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/plantillas/lote/validar", {
        body: {
          inscripcion_torneo_id: inscripcionTorneoId as number,
          fecha_inicio: fechaInicio,
          filas: filasParaEnvio(filas),
        },
      });
      if (error) throw error;
      return data as { validos: FilaValida[]; invalidos: FilaInvalida[] };
    },
    onSuccess: (data) => setModo({ tipo: "revision", validos: data.validos, invalidos: data.invalidos }),
  });

  const confirmarMutation = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/plantillas/lote/confirmar", {
        body: {
          inscripcion_torneo_id: inscripcionTorneoId as number,
          fecha_inicio: fechaInicio,
          filas: filasParaEnvio(filas),
        },
      });
      if (error) throw error;
      return data as { insertados: unknown[]; rechazados: FilaInvalida[] };
    },
    onSuccess: (data) => {
      setModo({ tipo: "resultado", insertados: data.insertados.length, rechazados: data.rechazados });
      if (data.rechazados.length === 0) {
        equipos.listQuery.refetch();
      }
    },
  });

  function agregarFila() {
    setFilas((f) => [...f, { ...FILA_VACIA }]);
  }
  function quitarFila(idx: number) {
    setFilas((f) => f.filter((_, i) => i !== idx));
  }
  function actualizarFila(idx: number, campo: keyof Fila, valor: string) {
    setFilas((f) => f.map((fila, i) => (i === idx ? { ...fila, [campo]: valor } : fila)));
  }

  const puedeValidar =
    inscripcionTorneoId != null &&
    fechaInicio !== "" &&
    filasParaEnvio(filas).length > 0 &&
    filasParaEnvio(filas).every((f) => f.cedula && f.nombre && f.correo_electronico);

  if (modo.tipo === "formulario") {
    return (
      <div className="page">
        <h1>Registro por lote</h1>
        {preResuelto ? (
          <p className="muted">
            Equipo: <strong>{preResuelto.contexto}</strong>
          </p>
        ) : (
          <div className="resource-form">
            <label>
              {alcanceTorneo ? "Equipo" : "Torneo — Equipo"}
              <select
                value={inscripcionTorneoId ?? ""}
                onChange={(e) => setInscripcionTorneoId(e.target.value ? Number(e.target.value) : null)}
                disabled={inscripciones.listQuery.isLoading}
              >
                <option value="">Elegir...</option>
                {(inscripciones.listQuery.data ?? []).map((i) => (
                  <option key={i.id} value={i.id}>
                    {etiquetaInscripcion(i)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Fecha de inicio
              <input type="date" value={fechaInicio} onChange={(e) => setFechaInicio(e.target.value)} />
            </label>
          </div>
        )}

        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Cédula</th>
                <th>Nombre</th>
                <th>Dorsal</th>
                <th>Correo</th>
                <th></th>
              </tr>
            </thead>
            <tbody>
              {filas.map((fila, idx) => (
                <tr key={idx}>
                  <td>
                    <input
                      aria-label={`Cédula fila ${idx + 1}`}
                      value={fila.cedula}
                      onChange={(e) => actualizarFila(idx, "cedula", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Nombre fila ${idx + 1}`}
                      value={fila.nombre}
                      onChange={(e) => actualizarFila(idx, "nombre", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Dorsal fila ${idx + 1}`}
                      type="number"
                      value={fila.dorsal}
                      onChange={(e) => actualizarFila(idx, "dorsal", e.target.value)}
                    />
                  </td>
                  <td>
                    <input
                      aria-label={`Correo fila ${idx + 1}`}
                      value={fila.correo_electronico}
                      onChange={(e) => actualizarFila(idx, "correo_electronico", e.target.value)}
                    />
                  </td>
                  <td>
                    {filas.length > 1 && (
                      <button type="button" className="link-button" onClick={() => quitarFila(idx)}>
                        Quitar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <button type="button" className="link-button" onClick={agregarFila}>
          + agregar fila
        </button>

        {validarMutation.isError && (
          <p className="error-text">
            {apiErrorMessage(validarMutation.error)}{" "}
            <button type="button" onClick={() => validarMutation.mutate()}>
              Reintentar
            </button>
          </p>
        )}

        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={() => navigate(volverDestino)}>
            Cancelar
          </button>
          <button
            type="button"
            disabled={!puedeValidar || validarMutation.isPending}
            onClick={() => validarMutation.mutate()}
          >
            {validarMutation.isPending ? "Validando..." : "Validar"}
          </button>
        </div>
      </div>
    );
  }

  if (modo.tipo === "revision") {
    const { validos, invalidos } = modo;
    return (
      <div className="page">
        <h1>Revisar registro por lote</h1>
        <section>
          <h2>✅ Válidos ({validos.length})</h2>
          {validos.length === 0 ? (
            <p className="muted">Ningún jugador nuevo listo para registrar.</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Cédula</th>
                    <th>Nombre</th>
                    <th>Dorsal</th>
                    <th>Correo</th>
                  </tr>
                </thead>
                <tbody>
                  {validos.map((f) => (
                    <tr key={f.fila_index}>
                      <td>{f.cedula}</td>
                      <td>{f.nombre}</td>
                      <td>{f.dorsal ?? "—"}</td>
                      <td>{f.correo_electronico}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>

        {invalidos.length > 0 && (
          <section>
            <h2 className="warning-text">⚠️ Inválidos ({invalidos.length})</h2>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Cédula</th>
                    <th>Nombre</th>
                    <th>Motivo</th>
                  </tr>
                </thead>
                <tbody>
                  {invalidos.map((f) => (
                    <tr key={f.fila_index}>
                      <td>{f.cedula}</td>
                      <td>{f.nombre}</td>
                      <td>{f.motivo}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>
        )}

        {confirmarMutation.isError && <p className="error-text">{apiErrorMessage(confirmarMutation.error)}</p>}

        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={() => setModo({ tipo: "formulario" })}>
            Cancelar registro
          </button>
          <button
            type="button"
            disabled={validos.length === 0 || confirmarMutation.isPending}
            onClick={() => confirmarMutation.mutate()}
          >
            {confirmarMutation.isPending ? "Confirmando..." : "Confirmar"}
          </button>
        </div>
      </div>
    );
  }

  // resultado
  if (modo.rechazados.length === 0) {
    return (
      <div className="page">
        <h1>Registro por lote</h1>
        <p className="success-text">{modo.insertados} jugador(es) registrado(s).</p>
        <button type="button" onClick={() => navigate(volverDestino)}>
          {volverLabel}
        </button>
      </div>
    );
  }
  return (
    <div className="page">
      <h1>Registro por lote — resultado parcial</h1>
      <p className="success-text">{modo.insertados} de {modo.insertados + modo.rechazados.length} jugador(es) registrado(s).</p>
      <section>
        <h2 className="warning-text">⚠️ No se pudieron registrar ({modo.rechazados.length})</h2>
        <div className="table-scroll">
          <table>
            <thead>
              <tr>
                <th>Cédula</th>
                <th>Nombre</th>
                <th>Motivo</th>
              </tr>
            </thead>
            <tbody>
              {modo.rechazados.map((f) => (
                <tr key={f.fila_index}>
                  <td>{f.cedula}</td>
                  <td>{f.nombre}</td>
                  <td>{f.motivo}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
      <div className="resource-form__actions">
        <button type="button" onClick={() => navigate(volverDestino)}>
          {volverLabel}
        </button>
        <button
          type="button"
          onClick={() => {
            // Recupera correo_electronico/dorsal de `filas` (el estado del
            // formulario, todavía intacto — no se pisa hasta este punto) en
            // vez de dejarlos en blanco: fila_index es la posición que esa
            // fila tenía en el envío original, así que sigue siendo válida
            // acá. Sin esto el admin tenía que retipear datos que ya había
            // cargado, solo por corregir el motivo del rechazo.
            const rechazadas = modo.rechazados;
            setFilas(
              rechazadas.map((r) => {
                const original = filas[r.fila_index];
                return {
                  cedula: r.cedula,
                  nombre: r.nombre,
                  correo_electronico: original?.correo_electronico ?? "",
                  dorsal: original?.dorsal ?? "",
                };
              }),
            );
            setModo({ tipo: "formulario" });
          }}
        >
          Volver al formulario (solo las rechazadas)
        </button>
      </div>
    </div>
  );
}
