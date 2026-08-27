import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";

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
  cedula: string;
  correo_electronico: string;
  disciplinas: PerfilDisciplina[];
}

const badgePorEstado: Record<PerfilDisciplina["estado"], string> = {
  Activo: "badge badge--en-curso",
  Suspendido: "badge badge--suspendido",
  Libre: "badge badge--libre",
};

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");
const formatearFechaHora = (iso: string) => new Date(iso).toLocaleString("es-AR");

/** Perfil de Jugador: stats + trayectoria consolidadas por disciplina
 * (equipos-jugadores-plan.md, Fase 2, Etapa D). No usa useResourceCrud —
 * es la lectura de un solo recurso anidado (GET /jugadores/{id}/perfil),
 * no una colección CRUD. Se llega vía el link "Ver perfil" en
 * JugadoresAdmin.tsx, sin pestaña propia (mismo criterio que
 * /partido/:partidoId/en-vivo). */
export function PerfilJugadorAdminPage() {
  const { jugadorId } = useParams<{ jugadorId: string }>();

  const query = useQuery({
    queryKey: ["perfil-jugador", jugadorId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/jugadores/{jugador_id}/perfil", {
        params: { path: { jugador_id: Number(jugadorId) } },
      });
      if (error) throw error;
      return data as PerfilJugador;
    },
  });

  if (query.isLoading) return <p>Cargando...</p>;
  if (query.isError) return <p className="error-text">{apiErrorMessage(query.error)}</p>;
  const perfil = query.data;
  if (!perfil) return null;

  return (
    <div className="page">
      <Link to="/torneo-admin/jugadores">← Volver a Jugadores</Link>
      <h1>{perfil.nombre}</h1>
      <p className="muted">
        Cédula: {perfil.cedula} — Correo: {perfil.correo_electronico}
      </p>

      {perfil.disciplinas.length === 0 && <p className="muted">Sin perfiles de disciplina todavía.</p>}

      {perfil.disciplinas.map((d) => (
        <section key={d.jugador_perfil_id} className="card">
          <h2>
            {d.disciplina} <span className={badgePorEstado[d.estado]}>{d.estado}</span>
          </h2>
          <p>Goles totales: {d.goles_totales}</p>

          <h3>Equipos activos</h3>
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

          <h3>Trayectoria</h3>
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
    </div>
  );
}
