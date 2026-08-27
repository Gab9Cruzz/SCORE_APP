import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../../../api/client";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import type { RegistroLotePreResuelto } from "../RegistroLoteAdmin";

interface EquipoRow {
  id: number;
  nombre: string;
  estado: string;
}
interface ModalidadRow {
  id: number;
  nombre: string;
  disciplina_id: number;
  tamano_equipo: number;
}
interface FilaPlantilla {
  cedula: string;
  nombre: string;
  correo_electronico: string;
  dorsal: string;
}

const FILA_VACIA: FilaPlantilla = { cedula: "", nombre: "", correo_electronico: "", dorsal: "" };

interface ModalAgregarEquipoProps {
  torneoId: number;
  /** Para armar el "contexto" que ve RegistroLoteAdminPage y el texto de
   * vuelta — ej. "Liga Relámpago — Edición 2". */
  torneoContexto: string;
  /** modalidad_id del TORNEO (no de un equipo) — para saber si esta
   * disciplina es de tamaño 1 (torneos-admin-plan.md, D-Eng-4: auto-nombrar
   * el equipo cuando el "equipo" es en realidad un jugador individual). */
  torneoModalidadId: number | null;
  equiposYaInscritosIds: Set<number>;
  onClose: () => void;
}

type Modo = { tipo: "buscar" } | { tipo: "crear" };

/** Modal "Agregar Equipo" (torneos-admin-plan.md, Fase 2, journey pasos
 * 3-5): buscar un equipo existente e inscribirlo, o crear uno nuevo —
 * ambos caminos en la misma ventana, sin saltos de contexto (Decision
 * Audit Trail #4). Crear nuevo encadena equipo → inscripción → dispara la
 * pantalla dividida ya existente (RegistroLoteAdminPage) con el contexto
 * ya resuelto, en vez de reconstruir ese flujo acá adentro (P4 DRY). */
export function ModalAgregarEquipo(props: ModalAgregarEquipoProps) {
  const { torneoId, torneoContexto, torneoModalidadId, equiposYaInscritosIds, onClose } = props;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [modo, setModo] = useState<Modo>({ tipo: "buscar" });
  const [busqueda, setBusqueda] = useState("");
  const [nombreNuevoEquipo, setNombreNuevoEquipo] = useState("");
  const [nombreEditadoAMano, setNombreEditadoAMano] = useState(false);
  const [filas, setFilas] = useState<FilaPlantilla[]>([{ ...FILA_VACIA }]);
  const [inscribiendoId, setInscribiendoId] = useState<number | null>(null);

  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });
  const modalidades = useResourceCrud<ModalidadRow>({ resourceKey: "modalidades", basePath: "/api/v1/modalidades" });

  const modalidadDelTorneo = useMemo(
    () => (modalidades.listQuery.data ?? []).find((m) => m.id === torneoModalidadId),
    [modalidades.listQuery.data, torneoModalidadId],
  );
  const esIndividual = modalidadDelTorneo?.tamano_equipo === 1;

  const equiposDisponibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return (equipos.listQuery.data ?? []).filter(
      (e) => !equiposYaInscritosIds.has(e.id) && (texto === "" || e.nombre.toLowerCase().includes(texto)),
    );
  }, [equipos.listQuery.data, equiposYaInscritosIds, busqueda]);

  const inscribirExistente = useMutation({
    mutationFn: async (equipoId: number) => {
      const { data, error } = await api.POST("/api/v1/inscripciones", {
        body: { torneo_id: torneoId, equipo_id: equipoId },
      } as never);
      if (error) throw error;
      return data;
    },
    onMutate: (equipoId) => setInscribiendoId(equipoId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["inscripciones"] });
      setInscribiendoId(null);
    },
    onError: () => setInscribiendoId(null),
  });

  const crearYRegistrar = useMutation({
    mutationFn: async () => {
      const { data: equipo, error: errEquipo } = await api.POST("/api/v1/equipos", {
        body: { nombre: nombreNuevoEquipo.trim() },
      } as never);
      if (errEquipo) throw errEquipo;
      const equipoId = (equipo as { id: number }).id;

      const { data: inscripcion, error: errInsc } = await api.POST("/api/v1/inscripciones", {
        body: { torneo_id: torneoId, equipo_id: equipoId },
      } as never);
      if (errInsc) throw errInsc;
      return { inscripcionTorneoId: (inscripcion as { id: number }).id, equipoNombre: nombreNuevoEquipo.trim() };
    },
    onSuccess: ({ inscripcionTorneoId, equipoNombre }) => {
      queryClient.invalidateQueries({ queryKey: ["inscripciones"] });
      queryClient.invalidateQueries({ queryKey: ["equipos"] });
      const preResuelto: RegistroLotePreResuelto = {
        inscripcionTorneoId,
        contexto: `${equipoNombre} — ${torneoContexto}`,
        volverA: `/torneo-admin/torneos/${torneoId}/equipos`,
      };
      navigate("/torneo-admin/plantillas/lote", { state: preResuelto });
    },
  });

  function actualizarFila(idx: number, campo: keyof FilaPlantilla, valor: string) {
    setFilas((f) => f.map((fila, i) => (i === idx ? { ...fila, [campo]: valor } : fila)));
    // D-Eng-4: en disciplinas de tamaño 1 (Tenis Individual, Pádel...) no
    // tiene sentido pedirle al admin que invente un nombre de "equipo"
    // para un deporte de un jugador solo — se autocompleta con el nombre
    // de la primera fila, editable igual si prefiere otro.
    if (esIndividual && idx === 0 && campo === "nombre" && !nombreEditadoAMano) {
      setNombreNuevoEquipo(valor);
    }
  }

  const filasConDato = filas.filter((f) => f.cedula.trim() !== "" || f.nombre.trim() !== "");
  const puedeCrear =
    nombreNuevoEquipo.trim() !== "" &&
    filasConDato.length > 0 &&
    filasConDato.every((f) => f.cedula.trim() && f.nombre.trim() && f.correo_electronico.trim());

  return (
    <div className="modal-overlay" role="dialog" aria-label="Agregar equipo">
      <div className="modal-panel">
        {modo.tipo === "buscar" && (
          <>
            <h2>Agregar equipo</h2>
            <input
              aria-label="Buscar equipo existente"
              placeholder="Buscar equipo..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
            {equipos.listQuery.isLoading && <p>Cargando...</p>}
            {!equipos.listQuery.isLoading && equiposDisponibles.length === 0 && (
              <p className="muted">No hay equipos con ese nombre. ¿Es nuevo?</p>
            )}
            {equiposDisponibles.map((e) => (
              <div key={e.id} className="modal-panel__equipo-fila">
                <span>{e.nombre}</span>
                <button
                  type="button"
                  disabled={inscribiendoId === e.id}
                  onClick={() => inscribirExistente.mutate(e.id)}
                >
                  {inscribiendoId === e.id ? "Inscribiendo..." : "Inscribir"}
                </button>
              </div>
            ))}
            {inscribirExistente.isError && (
              <p className="error-text">{apiErrorMessage(inscribirExistente.error)}</p>
            )}
            <p className="modal-panel__separador">— o —</p>
            <button type="button" onClick={() => setModo({ tipo: "crear" })}>
              + Crear equipo nuevo
            </button>
            <div className="resource-form__actions">
              <button type="button" className="link-button" onClick={onClose}>
                Cerrar
              </button>
            </div>
          </>
        )}

        {modo.tipo === "crear" && (
          <>
            <h2>Crear equipo nuevo — {torneoContexto}</h2>
            <div className="resource-form">
              <label>
                Nombre del equipo
                <input
                  value={nombreNuevoEquipo}
                  onChange={(e) => {
                    setNombreNuevoEquipo(e.target.value);
                    setNombreEditadoAMano(true);
                  }}
                />
              </label>
            </div>
            <p className="muted">Plantilla inicial (obligatoria):</p>
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>Cédula</th>
                    <th>Nombre</th>
                    <th>Correo</th>
                    <th>Dorsal</th>
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
                          aria-label={`Correo fila ${idx + 1}`}
                          value={fila.correo_electronico}
                          onChange={(e) => actualizarFila(idx, "correo_electronico", e.target.value)}
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
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!esIndividual && (
              <button type="button" className="link-button" onClick={() => setFilas((f) => [...f, { ...FILA_VACIA }])}>
                + agregar fila
              </button>
            )}
            {crearYRegistrar.isError && <p className="error-text">{apiErrorMessage(crearYRegistrar.error)}</p>}
            <div className="resource-form__actions">
              <button type="button" className="link-button" onClick={() => setModo({ tipo: "buscar" })}>
                Cancelar
              </button>
              <button
                type="button"
                disabled={!puedeCrear || crearYRegistrar.isPending}
                onClick={() => crearYRegistrar.mutate()}
              >
                {crearYRegistrar.isPending ? "Creando..." : "Validar y crear"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
