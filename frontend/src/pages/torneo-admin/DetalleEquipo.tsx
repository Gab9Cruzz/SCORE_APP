import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { useCatalogo } from "../../hooks/useCatalogo";
import { useResourceCrud } from "../../hooks/useResourceCrud";
import { iconoDisciplina } from "./iconosDisciplina";

interface EquipoDetalle {
  id: number;
  nombre: string;
  disciplina_id: number;
  modalidad_id: number;
  estado: string;
}
interface PlantillaBaseRow {
  id: number;
  equipo_id: number;
  jugador_perfil_id: number;
  jugador_id: number;
  jugador_nombre: string;
  jugador_cedula: string;
  dorsal_sugerido: number | null;
  estado: string;
}
interface JugadorRow {
  id: number;
  nombre: string;
  cedula: string;
  estado: string;
}
interface InscripcionRow {
  id: number;
  torneo_id: number;
}

/** Detalle del Equipo (gestion-avanzada-equipos-control-mesa-plan.md,
 * Flujo 1) — a donde `irAInscribir`/la creación de un equipo redirigen
 * ahora: la Plantilla Base (D1-C) queda habilitada de entrada, sin
 * depender de que exista un torneo. "Inscribir a un torneo" pasa a ser
 * una acción SECUNDARIA dentro de esta misma vista, visible solo si el
 * equipo todavía no tiene ninguna inscripción. */
export function DetalleEquipoPage() {
  const { equipoId: equipoIdParam } = useParams<{ equipoId: string }>();
  const equipoId = Number(equipoIdParam);
  const navigate = useNavigate();
  const catalogo = useCatalogo();
  const [buscando, setBuscando] = useState(false);

  const equipoQuery = useQuery({
    queryKey: ["equipo", equipoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/equipos/{equipo_id}", {
        params: { path: { equipo_id: equipoId } },
      });
      if (error) throw error;
      return data as EquipoDetalle;
    },
  });

  const plantillaBase = useResourceCrud<PlantillaBaseRow>({
    resourceKey: `plantilla-base-${equipoId}`,
    basePath: `/api/v1/equipos/${equipoId}/plantilla-base`,
  });

  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: { equipo_id: equipoId },
  });

  const filas = plantillaBase.listQuery.data ?? [];
  const sinInscripciones = (inscripciones.listQuery.data ?? []).length === 0;

  if (equipoQuery.isLoading) return <div className="page"><p>Cargando...</p></div>;
  if (equipoQuery.isError || !equipoQuery.data) {
    return (
      <div className="page">
        <p className="error-text">No se pudo cargar el equipo.</p>
      </div>
    );
  }
  const equipo = equipoQuery.data;
  const emoji = iconoDisciplina(catalogo.nombreDisciplina(equipo.disciplina_id));

  return (
    <div className="page">
      <button type="button" className="link-button" onClick={() => navigate("/torneo-admin/equipos")}>
        ← Equipos
      </button>
      <div className="page__header">
        <h1>
          {emoji ? `${emoji} ` : ""}
          {equipo.nombre}
        </h1>
        <span className="badge">{equipo.estado}</span>
      </div>
      <p className="muted">
        {catalogo.nombreDisciplina(equipo.disciplina_id)} · {catalogo.nombreModalidad(equipo.modalidad_id)}
      </p>

      <section className="card">
        <div className="page__header">
          <h2>Plantilla Base ({filas.length} jugador{filas.length === 1 ? "" : "es"})</h2>
          <button type="button" onClick={() => setBuscando(true)}>
            + Buscar/Agregar jugador
          </button>
        </div>

        {plantillaBase.softDelete.isError && (
          <p className="error-text">{apiErrorMessage(plantillaBase.softDelete.error)}</p>
        )}

        {plantillaBase.listQuery.isLoading && <p>Cargando...</p>}
        {plantillaBase.listQuery.isError && <p className="error-text">No se pudo cargar la plantilla base.</p>}
        {!plantillaBase.listQuery.isLoading && filas.length === 0 && (
          <p className="muted">Sin jugadores todavía. Buscá o creá el primero.</p>
        )}
        {filas.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Cédula</th>
                  <th>Nombre</th>
                  <th>Dorsal sugerido</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {filas.map((f) => (
                  <tr key={f.id}>
                    <td>{f.jugador_cedula}</td>
                    <td>{f.jugador_nombre}</td>
                    <td>{f.dorsal_sugerido ?? "—"}</td>
                    <td className="table-actions">
                      <button
                        type="button"
                        disabled={plantillaBase.softDelete.isPending}
                        onClick={() => plantillaBase.softDelete.mutate(f.id)}
                      >
                        Quitar
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {sinInscripciones && !inscripciones.listQuery.isLoading && (
        <p className="muted nota-plantilla">
          Este equipo aún no está inscrito a ningún torneo.{" "}
          <button
            type="button"
            className="link-button"
            onClick={() => navigate(`/torneo-admin/torneos?disciplina_id=${equipo.disciplina_id}`)}
          >
            Inscribir a un torneo →
          </button>
        </p>
      )}

      {buscando && (
        <ModalBuscarAgregarJugador
          equipoId={equipoId}
          equipoNombre={equipo.nombre}
          onAgregado={(dorsal) =>
            plantillaBase.create.mutate({ jugador_id: dorsal.jugador_id, dorsal_sugerido: dorsal.dorsal } as never)
          }
          onClose={() => setBuscando(false)}
        />
      )}
    </div>
  );
}

const JUGADOR_VACIO = { cedula: "", nombre: "", correo_electronico: "" };

/** Flujo 2 del plan: buscador con debounce (GET /jugadores?q=) + alerta
 * de multimilitancia (Nivel 1 del algoritmo, no bloqueante) antes de
 * confirmar. Sin conflicto, agrega directo sin modal. */
function ModalBuscarAgregarJugador(props: {
  equipoId: number;
  equipoNombre: string;
  onAgregado: (args: { jugador_id: number; dorsal: number | null }) => void;
  onClose: () => void;
}) {
  const { equipoId, onAgregado, onClose } = props;
  const [texto, setTexto] = useState("");
  const [textoDebounced, setTextoDebounced] = useState("");
  const [creando, setCreando] = useState(false);
  const [nuevoJugador, setNuevoJugador] = useState(JUGADOR_VACIO);
  const [confirmando, setConfirmando] = useState<{
    jugador: JugadorRow;
    conflicto: { conflicto: boolean; equipos: string[]; mensaje?: string | null };
  } | null>(null);

  // Debounce 300ms (Flujo 2 del plan).
  useDebouncedEffect(texto, 300, setTextoDebounced);

  const resultadosQuery = useQuery({
    queryKey: ["jugadores-buscar", textoDebounced],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/jugadores", {
        params: { query: { q: textoDebounced, limit: 20 } },
      });
      if (error) throw error;
      return data as JugadorRow[];
    },
    enabled: textoDebounced.trim() !== "",
  });

  const crearJugador = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });

  async function elegirJugador(jugador: JugadorRow) {
    const { data, error } = await api.GET("/api/v1/equipos/{equipo_id}/plantilla-base/verificar", {
      params: { path: { equipo_id: equipoId }, query: { jugador_id: jugador.id } },
    });
    if (error) return;
    if (data.conflicto) {
      setConfirmando({ jugador, conflicto: data });
    } else {
      onAgregado({ jugador_id: jugador.id, dorsal: null });
      onClose();
    }
  }

  const pareceCedula = /^\d+$/.test(texto.trim());
  const puedeCrear = nuevoJugador.cedula.trim() !== "" && nuevoJugador.nombre.trim() !== "" && nuevoJugador.correo_electronico.trim() !== "";

  if (confirmando) {
    // Flujo 2: modal bloqueante, texto literal — el admin tiene que
    // leerlo completo, no un warning que se pueda ignorar sin leer.
    return (
      <div className="modal-overlay" role="dialog" aria-label="Advertencia de multimilitancia">
        <div className="modal-panel">
          <p>
            ⚠️ {confirmando.jugador.nombre} ya está inscrito en {confirmando.conflicto.equipos.join(", ")}.
          </p>
          <p>{confirmando.conflicto.mensaje}</p>
          <div className="resource-form__actions">
            <button type="button" className="link-button" onClick={() => setConfirmando(null)}>
              Cancelar
            </button>
            <button
              type="button"
              onClick={() => {
                onAgregado({ jugador_id: confirmando.jugador.id, dorsal: null });
                onClose();
              }}
            >
              Agregar igual
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="modal-overlay" role="dialog" aria-label="Buscar o agregar jugador">
      <div className="modal-panel">
        <h2>Buscar por nombre o cédula — {props.equipoNombre}</h2>
        <input
          aria-label="Buscar jugador"
          placeholder="Nombre o cédula..."
          value={texto}
          onChange={(e) => setTexto(e.target.value)}
          autoFocus
        />

        {textoDebounced.trim() !== "" && !resultadosQuery.isLoading && (resultadosQuery.data ?? []).length === 0 && (
          <p className="muted">Ningún jugador coincide con "{textoDebounced}".</p>
        )}
        {(resultadosQuery.data ?? []).map((j) => (
          <div key={j.id} className="modal-panel__equipo-fila">
            <span>
              {j.nombre} — {j.cedula}
            </span>
            <button type="button" onClick={() => elegirJugador(j)}>
              Agregar
            </button>
          </div>
        ))}

        <p className="modal-panel__separador">— o —</p>
        {!creando ? (
          <button
            type="button"
            onClick={() => {
              setCreando(true);
              setNuevoJugador({
                ...JUGADOR_VACIO,
                cedula: pareceCedula ? texto.trim() : "",
                nombre: pareceCedula ? "" : texto.trim(),
              });
            }}
          >
            + Crear jugador nuevo
          </button>
        ) : (
          <div className="resource-form">
            <label>
              Cédula
              <input
                value={nuevoJugador.cedula}
                onChange={(e) => setNuevoJugador((j) => ({ ...j, cedula: e.target.value }))}
              />
            </label>
            <label>
              Nombre
              <input
                value={nuevoJugador.nombre}
                onChange={(e) => setNuevoJugador((j) => ({ ...j, nombre: e.target.value }))}
              />
            </label>
            <label>
              Correo
              <input
                value={nuevoJugador.correo_electronico}
                onChange={(e) => setNuevoJugador((j) => ({ ...j, correo_electronico: e.target.value }))}
              />
            </label>
            {crearJugador.create.isError && (
              <p className="error-text">{apiErrorMessage(crearJugador.create.error)}</p>
            )}
            <div className="resource-form__actions">
              <button
                type="button"
                disabled={!puedeCrear || crearJugador.create.isPending}
                onClick={() =>
                  crearJugador.create.mutate(
                    {
                      nombre: nuevoJugador.nombre.trim(),
                      cedula: nuevoJugador.cedula.trim(),
                      correo_electronico: nuevoJugador.correo_electronico.trim(),
                    } as never,
                    { onSuccess: (jugador) => elegirJugador(jugador as JugadorRow) },
                  )
                }
              >
                {crearJugador.create.isPending ? "Creando..." : "Crear y agregar"}
              </button>
            </div>
          </div>
        )}

        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

/** Debounce mínimo sin librería extra — sincroniza `setter(value)` 300ms
 * después de que el usuario deja de tipear (Flujo 2 del plan). */
function useDebouncedEffect(value: string, delayMs: number, setter: (v: string) => void) {
  useEffect(() => {
    const id = setTimeout(() => setter(value), delayMs);
    return () => clearTimeout(id);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);
}
