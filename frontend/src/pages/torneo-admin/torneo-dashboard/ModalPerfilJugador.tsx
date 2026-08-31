import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api, apiErrorMessage } from "../../../api/client";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import { AvatarJugador } from "../AvatarJugador";

interface EquipoActivo {
  inscripcion_torneo_id: number;
  torneo: string;
  equipo: string;
  dorsal: number | null;
  fecha_inicio: string;
}
interface Trayectoria {
  id: number;
  fecha_traspaso: string;
  origen: string | null;
  destino: string;
  motivo: string | null;
  estado: string;
}
interface PerfilDisciplina {
  jugador_perfil_id: number;
  disciplina: string;
  estado: "Libre" | "Activo" | "Suspendido";
  goles_totales: number;
  equipos_activos: EquipoActivo[];
  trayectoria: Trayectoria[];
}
interface PerfilJugador {
  jugador_id: number;
  nombre: string;
  foto_url: string | null;
  cedula: string;
  correo_electronico: string;
  disciplinas: PerfilDisciplina[];
}
interface JugadorRow {
  id: number;
  nombre: string;
  cedula: string;
  correo_electronico: string;
  foto_url: string | null;
}

const badgePorEstado: Record<PerfilDisciplina["estado"], string> = {
  Activo: "badge badge--en-curso",
  Suspendido: "badge badge--suspendido",
  Libre: "badge badge--libre",
};

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");
const formatearFechaHora = (iso: string) => new Date(iso).toLocaleString("es-AR");

interface ModalPerfilJugadorProps {
  jugadorId: number;
  onClose: () => void;
}

/** Modal de Perfil de Jugador — Design sección D del plan
 * (motor-formatos-plantillas-navegacion-plan.md). Se abre desde una
 * tarjeta del grid de Plantillas: un modal (no una navegación a página
 * nueva) mantiene el contexto — "vengo del grid, corrijo un typo, sigo
 * viendo el grid" (Decisión Audit #7). Mismos datos que
 * PerfilJugadorAdminPage (que sigue existiendo para el acceso desde el
 * listado global de JugadoresAdmin.tsx), más edición: PATCH
 * /jugadores/{id} ya existía en el backend sin ningún consumidor
 * (Decisión P8 del plan). */
export function ModalPerfilJugador(props: ModalPerfilJugadorProps) {
  const { jugadorId, onClose } = props;
  const queryClient = useQueryClient();
  const [editando, setEditando] = useState(false);
  const [form, setForm] = useState({ nombre: "", cedula: "", correo_electronico: "" });

  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });

  const query = useQuery({
    queryKey: ["perfil-jugador", jugadorId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/jugadores/{jugador_id}/perfil", {
        params: { path: { jugador_id: jugadorId } },
      });
      if (error) throw error;
      return data as PerfilJugador;
    },
  });

  function abrirEdicion() {
    if (!query.data) return;
    setForm({ nombre: query.data.nombre, cedula: query.data.cedula, correo_electronico: query.data.correo_electronico });
    setEditando(true);
  }

  function guardar() {
    jugadores.update.mutate(
      { id: jugadorId, body: form as never },
      {
        onSuccess: () => {
          // Refresca el perfil (este modal) y las listas de jugadores que
          // ya tenían este nombre cacheado (grid de Plantillas, ResourceTable
          // de JugadoresAdmin) — mismo criterio que invalidate() del hook.
          queryClient.invalidateQueries({ queryKey: ["perfil-jugador", jugadorId] });
          setEditando(false);
        },
      },
    );
  }

  const perfil = query.data;

  return (
    <div className="modal-overlay" role="dialog" aria-label="Perfil de Jugador">
      <div className="modal-panel">
        {query.isLoading && <p>Cargando...</p>}
        {query.isError && <p className="error-text">{apiErrorMessage(query.error)}</p>}

        {perfil && !editando && (
          <>
            <div className="perfil-jugador__header">
              <AvatarJugador jugadorId={perfil.jugador_id} nombre={perfil.nombre} fotoUrl={perfil.foto_url} tamano="grande" />
              <div className="perfil-jugador__datos">
                <h2>{perfil.nombre}</h2>
                <p className="muted">
                  Cédula: {perfil.cedula} — Correo: {perfil.correo_electronico}
                </p>
              </div>
              <button type="button" onClick={abrirEdicion}>
                Editar
              </button>
            </div>

            {perfil.disciplinas.length === 0 && <p className="muted">Sin perfiles de disciplina todavía.</p>}

            {perfil.disciplinas.map((d) => (
              <section key={d.jugador_perfil_id} className="card">
                <h3>
                  {d.disciplina} <span className={badgePorEstado[d.estado]}>{d.estado}</span>
                </h3>
                <p>Goles totales: {d.goles_totales}</p>

                <h4>Equipos activos</h4>
                {d.equipos_activos.length === 0 ? (
                  <p className="muted">Sin equipos activos en esta disciplina.</p>
                ) : (
                  <ul>
                    {d.equipos_activos.map((e) => (
                      <li key={e.inscripcion_torneo_id}>
                        {e.torneo} — {e.equipo} {e.dorsal != null && `(dorsal #${e.dorsal})`} — desde{" "}
                        {formatearFecha(e.fecha_inicio)}
                      </li>
                    ))}
                  </ul>
                )}

                <h4>Trayectoria</h4>
                {d.trayectoria.length === 0 ? (
                  <p className="muted">Sin traspasos registrados en esta disciplina.</p>
                ) : (
                  <div className="table-scroll">
                    <table>
                      <thead>
                        <tr>
                          <th>Fecha</th>
                          <th>Origen</th>
                          <th>Destino</th>
                          <th>Motivo</th>
                          <th>Estado</th>
                        </tr>
                      </thead>
                      <tbody>
                        {d.trayectoria.map((t) => (
                          <tr key={t.id}>
                            <td>{formatearFechaHora(t.fecha_traspaso)}</td>
                            <td>{t.origen ?? "Agencia libre"}</td>
                            <td>{t.destino}</td>
                            <td>{t.motivo ?? "—"}</td>
                            <td>{t.estado}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </section>
            ))}

            <div className="resource-form__actions">
              <button type="button" className="link-button" onClick={onClose}>
                Cerrar
              </button>
            </div>
          </>
        )}

        {perfil && editando && (
          <>
            <h2>Editar datos personales</h2>
            <div className="resource-form">
              <label>
                Nombre
                <input value={form.nombre} onChange={(e) => setForm((f) => ({ ...f, nombre: e.target.value }))} />
              </label>
              <label>
                Cédula
                <input value={form.cedula} onChange={(e) => setForm((f) => ({ ...f, cedula: e.target.value }))} />
              </label>
              <label>
                Correo
                <input
                  value={form.correo_electronico}
                  onChange={(e) => setForm((f) => ({ ...f, correo_electronico: e.target.value }))}
                />
              </label>
              {/* Cédula duplicada (unique_jugador_cedula) llega acá como
                  mensaje inline, no un toast genérico — estados de
                  interacción del grid, Fase 2 del plan. */}
              {jugadores.update.isError && (
                <p className="error-text">{apiErrorMessage(jugadores.update.error, "No se pudo guardar.")}</p>
              )}
              <div className="resource-form__actions">
                <button type="button" className="link-button" onClick={() => setEditando(false)}>
                  Cancelar
                </button>
                <button type="button" disabled={jugadores.update.isPending} onClick={guardar}>
                  {jugadores.update.isPending ? "Guardando..." : "Guardar"}
                </button>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
