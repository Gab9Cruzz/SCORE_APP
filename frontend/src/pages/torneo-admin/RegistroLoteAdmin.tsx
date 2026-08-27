import { useMutation } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { useResourceCrud } from "../../hooks/useResourceCrud";

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
interface EquipoRow {
  id: number;
  nombre: string;
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
  const [modo, setModo] = useState<Modo>({ tipo: "formulario" });
  const [filas, setFilas] = useState<Fila[]>([{ ...FILA_VACIA }]);
  const [inscripcionTorneoId, setInscripcionTorneoId] = useState<number | null>(null);
  const [fechaInicio, setFechaInicio] = useState("");

  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });
  const torneos = useResourceCrud<TorneoRow>({ resourceKey: "torneos", basePath: "/api/v1/torneos" });
  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
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
        <div className="resource-form">
          <label>
            Torneo — Equipo
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
          <button type="button" className="link-button" onClick={() => navigate("/torneo-admin/plantillas")}>
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
        <button type="button" onClick={() => navigate("/torneo-admin/plantillas")}>
          Volver a Plantillas
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
        <button type="button" onClick={() => navigate("/torneo-admin/plantillas")}>
          Volver a Plantillas
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
