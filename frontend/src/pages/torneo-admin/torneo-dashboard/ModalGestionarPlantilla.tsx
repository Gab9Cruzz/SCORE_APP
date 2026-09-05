import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiErrorMessage } from "../../../api/client";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import { useEtiquetaJugadorPorPerfil } from "../../../hooks/useEtiquetaJugadorPorPerfil";
import type { RegistroLotePreResuelto } from "../RegistroLoteAdmin";

interface PlantillaRow {
  id: number;
  jugador_perfil_id: number;
  inscripcion_torneo_id: number;
  dorsal: number | null;
  estado: string;
}
interface JugadorRow {
  id: number;
  nombre: string;
  cedula: string;
  correo_electronico: string;
}
interface PerfilRow {
  id: number;
  jugador_id: number;
  disciplina_id: number;
}

interface FilaAlta {
  cedula: string;
  nombre: string;
  correo_electronico: string;
  dorsal: string;
}

const FILA_VACIA: FilaAlta = { cedula: "", nombre: "", correo_electronico: "", dorsal: "" };

const hoyISO = () => new Date().toISOString().slice(0, 10);

interface ModalGestionarPlantillaProps {
  inscripcionTorneoId: number;
  equipoNombre: string;
  torneoId: number;
  torneoContexto: string;
  disciplinaId: number;
  onClose: () => void;
}

/** Modal "Gestionar plantilla" — Design sección A del plan
 * (motor-formatos-plantillas-navegacion-plan.md). Consolida en una sola
 * pantalla lo que hoy vive repartido en dos (el conteo+botón "+ Agregar
 * jugadores" de EquiposDelTorneoPage, que saca al admin a Registro por
 * Lote, y el alta/baja individual de PlantillasDelTorneoPage, que actúa
 * sobre TODA la edición en vez de un equipo puntual): roster visible al
 * abrir, alta y baja sin salir de la pantalla, scoped a ESTE equipo+torneo.
 *
 * El link a Registro por Lote no desaparece — sigue siendo el camino
 * correcto para cargar varios jugadores nuevos de una vez con la pantalla
 * dividida de validación; este modal resuelve el caso de "agregar/quitar
 * uno o dos", que antes no tenía ningún atajo. */
export function ModalGestionarPlantilla(props: ModalGestionarPlantillaProps) {
  const { inscripcionTorneoId, equipoNombre, torneoId, torneoContexto, disciplinaId, onClose } = props;
  const navigate = useNavigate();

  const plantillas = useResourceCrud<PlantillaRow>({
    resourceKey: "plantillas",
    basePath: "/api/v1/plantillas",
    listParams: { inscripcion_torneo_id: inscripcionTorneoId },
  });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });
  const perfiles = useResourceCrud<PerfilRow, { jugador_id: number; disciplina_id: number }>({
    resourceKey: "perfiles",
    basePath: "/api/v1/perfiles",
    listParams: { disciplina_id: disciplinaId },
  });

  const nombreJugador = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j.nombre])),
    [jugadores.listQuery.data],
  );
  const perfilPorId = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [p.id, p])),
    [perfiles.listQuery.data],
  );
  // Bug 2 (D2, parte B): resolución dirigida — un perfil/jugador fuera de
  // la ventana de LIMITE_LISTA se pedía individual antes de caer al
  // fallback "Perfil #ID" (P3 del plan).
  const etiquetaJugador = useEtiquetaJugadorPorPerfil(
    (plantillas.listQuery.data ?? []).map((p) => p.jugador_perfil_id),
    perfilPorId,
    nombreJugador,
  );

  // Roster VIGENTE — mismo criterio que rosterCount en EquiposDelTorneo.tsx
  // (solo cuenta/lista Activo). Un jugador dado de baja sale de la vista
  // sin que la fila "desaparezca de golpe sin explicación": simplemente
  // deja de estar en este filtro (queda igual visible en la pestaña
  // Plantillas para quien busque el historial completo).
  const roster = useMemo(
    () => (plantillas.listQuery.data ?? []).filter((p) => p.estado === "Activo"),
    [plantillas.listQuery.data],
  );

  const [fila, setFila] = useState<FilaAlta>(FILA_VACIA);
  const [errorAlta, setErrorAlta] = useState<string | null>(null);
  const [resolviendo, setResolviendo] = useState(false);
  const [confirmandoBajaId, setConfirmandoBajaId] = useState<number | null>(null);

  // Resuelve-o-crea jugador+perfil, mismo patrón que ya usaban
  // PlantillasDelTorneo.crearVinculo (perfil) y
  // ModalAgregarInscripcion.ModalIndividual (búsqueda por cédula sobre la
  // lista ya cargada) — acá los dos pasos se juntan porque el mockup pide
  // Cédula/Nombre/Correo/Dorsal como un único formulario, no un picker de
  // jugador ya existente.
  async function agregarJugador() {
    setErrorAlta(null);
    const cedula = fila.cedula.trim();
    const nombre = fila.nombre.trim();
    const correo = fila.correo_electronico.trim();
    if (!cedula || !nombre || !correo) {
      setErrorAlta("Cédula, nombre y correo son obligatorios.");
      return;
    }

    setResolviendo(true);
    try {
      let jugador = (jugadores.listQuery.data ?? []).find((j) => j.cedula.trim() === cedula);
      // Mismo criterio que registro_lote.py (EC-2): la cédula ya
      // registrada con otro nombre no se sobreescribe silenciosamente.
      if (jugador && jugador.nombre.trim().toLowerCase() !== nombre.toLowerCase()) {
        setErrorAlta(`El nombre no coincide con el registrado para esta cédula (registrado: ${jugador.nombre})`);
        return;
      }
      if (!jugador) {
        jugador = await jugadores.create.mutateAsync({
          cedula,
          nombre,
          correo_electronico: correo,
        } as never);
      }

      let perfil = (perfiles.listQuery.data ?? []).find((p) => p.jugador_id === jugador!.id);
      if (!perfil) {
        perfil = await perfiles.create.mutateAsync({ jugador_id: jugador.id, disciplina_id: disciplinaId });
      }

      await plantillas.create.mutateAsync({
        jugador_perfil_id: perfil.id,
        inscripcion_torneo_id: inscripcionTorneoId,
        dorsal: fila.dorsal.trim() === "" ? null : Number(fila.dorsal),
        fecha_inicio: hoyISO(),
      } as never);
      setFila(FILA_VACIA);
    } catch (e) {
      // El dorsal duplicado (EC-45) y "ya juega en otro equipo" (exclusividad
      // de torneo) llegan acá con el mensaje específico que ahora da el
      // backend — no un 409/400 genérico.
      setErrorAlta(apiErrorMessage(e, "No se pudo agregar el jugador."));
    } finally {
      setResolviendo(false);
    }
  }

  // "Quitar" es un solo click, no un formulario de fecha (Design sección A):
  // manda fecha_fin=hoy directo. El caso de fecha retroactiva sigue
  // disponible desde la pestaña Plantillas (EC-47) — esto no le quita
  // funcionalidad, agrega el atajo del caso común.
  function confirmarBaja(row: PlantillaRow) {
    plantillas.customAction.mutate(
      { path: `/api/v1/plantillas/${row.id}/baja`, query: { fecha_fin: hoyISO() } },
      { onSuccess: () => setConfirmandoBajaId(null) },
    );
  }

  function irARegistroLote() {
    const contexto: RegistroLotePreResuelto = {
      inscripcionTorneoId,
      contexto: `${equipoNombre} — ${torneoContexto}`,
      volverA: `/torneo-admin/torneos/${torneoId}/equipos`,
    };
    navigate("/torneo-admin/plantillas/lote", { state: contexto });
  }

  const cargandoRoster =
    plantillas.listQuery.isLoading || jugadores.listQuery.isLoading || perfiles.listQuery.isLoading;

  return (
    <div className="modal-overlay" role="dialog" aria-label={`Gestionar plantilla — ${equipoNombre}`}>
      <div className="modal-panel">
        <h2>Gestionar plantilla — {equipoNombre}</h2>
        <p className="muted">{torneoContexto}</p>

        <h3>Jugadores actuales ({roster.length})</h3>
        {cargandoRoster && <p>Cargando...</p>}
        {!cargandoRoster && roster.length === 0 && (
          <p className="muted">Este equipo todavía no tiene jugadores en este torneo.</p>
        )}
        {!cargandoRoster && roster.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>Jugador</th>
                  <th>Dorsal</th>
                  <th>Estado</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {roster.map((r) => (
                  <tr key={r.id}>
                    <td>{etiquetaJugador(r.jugador_perfil_id)}</td>
                    <td>{r.dorsal != null ? `#${r.dorsal}` : "—"}</td>
                    <td>{r.estado}</td>
                    <td>
                      {confirmandoBajaId === r.id ? (
                        <span>
                          ¿Quitar a {etiquetaJugador(r.jugador_perfil_id)} de este equipo?{" "}
                          <button
                            type="button"
                            disabled={plantillas.customAction.isPending}
                            onClick={() => confirmarBaja(r)}
                          >
                            {plantillas.customAction.isPending ? "Quitando..." : "Sí, quitar"}
                          </button>{" "}
                          <button type="button" className="link-button" onClick={() => setConfirmandoBajaId(null)}>
                            Cancelar
                          </button>
                        </span>
                      ) : (
                        <button type="button" className="link-button" onClick={() => setConfirmandoBajaId(r.id)}>
                          Quitar
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <h3>+ Agregar jugador</h3>
        <div className="resource-form">
          <label>
            Cédula
            <input
              aria-label="Cédula"
              value={fila.cedula}
              onChange={(e) => setFila((f) => ({ ...f, cedula: e.target.value }))}
            />
          </label>
          <label>
            Nombre
            <input
              aria-label="Nombre"
              value={fila.nombre}
              onChange={(e) => setFila((f) => ({ ...f, nombre: e.target.value }))}
            />
          </label>
          <label>
            Correo
            <input
              aria-label="Correo"
              value={fila.correo_electronico}
              onChange={(e) => setFila((f) => ({ ...f, correo_electronico: e.target.value }))}
            />
          </label>
          <label>
            Dorsal
            <input
              aria-label="Dorsal"
              type="number"
              value={fila.dorsal}
              onChange={(e) => setFila((f) => ({ ...f, dorsal: e.target.value }))}
            />
          </label>
          {errorAlta && <p className="error-text">{errorAlta}</p>}
          <div className="resource-form__actions">
            <button type="button" disabled={resolviendo} onClick={agregarJugador}>
              {resolviendo ? "Agregando..." : "Agregar"}
            </button>
          </div>
        </div>

        <p className="modal-panel__separador">
          ¿Vas a cargar varios de una vez?{" "}
          <button type="button" className="link-button" onClick={irARegistroLote}>
            Registro por lote
          </button>
        </p>

        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}
