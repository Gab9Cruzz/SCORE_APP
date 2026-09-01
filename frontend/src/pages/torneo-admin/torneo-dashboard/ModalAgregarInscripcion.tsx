import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../../../api/client";
import { useCatalogo } from "../../../hooks/useCatalogo";
import { useResourceCrud } from "../../../hooks/useResourceCrud";
import type { RegistroLotePreResuelto } from "../RegistroLoteAdmin";

interface EquipoRow {
  id: number;
  nombre: string;
  disciplina_id: number;
  estado: string;
}
interface ModalidadRow {
  id: number;
  nombre: string;
  disciplina_id: number;
  tamano_equipo: number;
}
interface JugadorRow {
  id: number;
  nombre: string;
  cedula: string;
  correo_electronico: string;
  estado: string;
}
interface FilaPlantilla {
  cedula: string;
  nombre: string;
  correo_electronico: string;
  dorsal: string;
}

const FILA_VACIA: FilaPlantilla = { cedula: "", nombre: "", correo_electronico: "", dorsal: "" };
const JUGADOR_VACIO = { cedula: "", nombre: "", correo_electronico: "" };

interface ModalAgregarInscripcionProps {
  torneoId: number;
  /** Para armar el "contexto" que ve RegistroLoteAdminPage y el texto de
   * vuelta — ej. "Liga Relámpago — Edición 2". */
  torneoContexto: string;
  /** modalidad_id del TORNEO (no de un equipo/inscripción) — decide cuál de
   * los 3 caminos mostrar (ediciones-catalogo-disciplinas-plan.md, Fase 2
   * parte B): Tamano_Equipo == 1 → Individual (Jugador directo, sin
   * Equipo); == 2 → Pareja (Equipo autonombrado, exactamente 2 filas); > 2
   * → Conjunto (Equipo, nombre libre, sin cambios). */
  torneoModalidadId: number;
  /** disciplina_id del TORNEO. Es el filtro estricto del pedido B
   * (equipos-disciplina-navegacion-plan.md): solo se OFRECEN equipos de
   * esta disciplina, y el equipo que se cree acá nace con ella. La API
   * rechaza igual cualquier otra cosa (EC-33) — esto evita el viaje
   * redondo y, sobre todo, evita ofrecer una opción que no es opción. */
  torneoDisciplinaId: number;
  equiposYaInscritosIds: Set<number>;
  onClose: () => void;
}

type Modo = { tipo: "buscar" } | { tipo: "crear" };

/** Modal de inscripción a un torneo (ediciones-catalogo-disciplinas-plan.md,
 * Decisión B1 — reemplaza a ModalAgregarEquipo.tsx). Se ramifica en 3
 * caminos según Modalidad.tamano_equipo del torneo: Individual inscribe un
 * Jugador directo por POST /inscripciones, sin crear ninguna fila en
 * EQUIPOS — Pareja/Conjunto siguen el camino de Equipo que ya existía
 * (buscar uno existente o crear uno nuevo + plantilla inicial, encadenando
 * a la pantalla dividida de Registro por Lote — P4 DRY, no se reconstruye
 * ese flujo acá). */
export function ModalAgregarInscripcion(props: ModalAgregarInscripcionProps) {
  const { torneoId, torneoContexto, torneoModalidadId, torneoDisciplinaId, equiposYaInscritosIds, onClose } =
    props;

  const modalidades = useResourceCrud<ModalidadRow>({ resourceKey: "modalidades", basePath: "/api/v1/modalidades" });
  const modalidadDelTorneo = useMemo(
    () => (modalidades.listQuery.data ?? []).find((m) => m.id === torneoModalidadId),
    [modalidades.listQuery.data, torneoModalidadId],
  );
  const tamanoEquipo = modalidadDelTorneo?.tamano_equipo;

  // Espera a conocer tamanoEquipo antes de montar ModalIndividual/ModalEquipo:
  // ese valor decide, en el MOUNT, cuántas filas arranca la plantilla de
  // ModalEquipo (esPareja → 2 filas fijas) — si se montara antes con un
  // esPareja provisorio y después cambiara de prop, el useState de filas
  // no se reinicializa solo (la lazy init de useState solo corre una vez).
  if (tamanoEquipo == null) {
    return (
      <div className="modal-overlay" role="dialog" aria-label="Agregar inscripción">
        <div className="modal-panel">
          <p>Cargando...</p>
        </div>
      </div>
    );
  }

  if (tamanoEquipo === 1) {
    return <ModalIndividual torneoId={torneoId} torneoContexto={torneoContexto} onClose={onClose} />;
  }
  return (
    <ModalEquipo
      torneoId={torneoId}
      torneoContexto={torneoContexto}
      esPareja={tamanoEquipo === 2}
      torneoDisciplinaId={torneoDisciplinaId}
      torneoModalidadId={torneoModalidadId}
      equiposYaInscritosIds={equiposYaInscritosIds}
      onClose={onClose}
    />
  );
}

/** Camino Individual (Tamano_Equipo == 1) — sin ningún concepto de Equipo
 * en pantalla, ni en los mensajes de éxito/error (Litmus scorecard del
 * plan: "el admin nunca ve un concepto de Equipo en disciplinas
 * individuales"). Busca en el catálogo global de Jugadores por
 * cédula/nombre; si no aparece, se crea uno nuevo — mismo POST
 * /inscripciones en los dos casos (resuelve-o-crea del lado del backend,
 * D-Eng-6), esto solo decide qué datos precargar en el submit. */
function ModalIndividual(props: { torneoId: number; torneoContexto: string; onClose: () => void }) {
  const { torneoId, torneoContexto, onClose } = props;
  const queryClient = useQueryClient();
  const [busqueda, setBusqueda] = useState("");
  const [mostrarCrear, setMostrarCrear] = useState(false);
  const [nuevoJugador, setNuevoJugador] = useState(JUGADOR_VACIO);
  const [inscritoOk, setInscritoOk] = useState<string | null>(null);

  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });

  const jugadoresDisponibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    if (texto === "") return [];
    return (jugadores.listQuery.data ?? []).filter(
      (j) => j.cedula.toLowerCase().includes(texto) || j.nombre.toLowerCase().includes(texto),
    );
  }, [jugadores.listQuery.data, busqueda]);

  const inscribir = useMutation({
    mutationFn: async (jugador: { cedula: string; nombre: string; correo_electronico: string }) => {
      const { data, error } = await api.POST("/api/v1/inscripciones", {
        body: {
          torneo_id: torneoId,
          jugador_cedula: jugador.cedula.trim(),
          jugador_nombre: jugador.nombre.trim(),
          jugador_correo_electronico: jugador.correo_electronico.trim(),
        },
      } as never);
      if (error) throw error;
      return { data, nombre: jugador.nombre.trim() };
    },
    onSuccess: ({ nombre }) => {
      queryClient.invalidateQueries({ queryKey: ["inscripciones"] });
      queryClient.invalidateQueries({ queryKey: ["jugadores"] });
      setInscritoOk(`${nombre} inscrito`);
      setNuevoJugador(JUGADOR_VACIO);
      setMostrarCrear(false);
      setBusqueda("");
    },
  });

  const puedeCrear =
    nuevoJugador.cedula.trim() !== "" && nuevoJugador.nombre.trim() !== "" && nuevoJugador.correo_electronico.trim() !== "";

  return (
    <div className="modal-overlay" role="dialog" aria-label="Agregar jugador">
      <div className="modal-panel">
        <h2>Agregar jugador — {torneoContexto}</h2>
        <input
          aria-label="Buscar jugador existente"
          placeholder="Buscar por cédula o nombre..."
          value={busqueda}
          onChange={(e) => {
            setBusqueda(e.target.value);
            setInscritoOk(null);
          }}
        />
        {busqueda.trim() !== "" && jugadoresDisponibles.length === 0 && (
          <p className="muted">No hay jugadores con ese nombre/cédula. ¿Es nuevo?</p>
        )}
        {jugadoresDisponibles.map((j) => (
          <div key={j.id} className="modal-panel__equipo-fila">
            <span>
              {j.nombre} — {j.cedula}
            </span>
            <button type="button" disabled={inscribir.isPending} onClick={() => inscribir.mutate(j)}>
              {inscribir.isPending ? "Inscribiendo..." : "Inscribir"}
            </button>
          </div>
        ))}

        <p className="modal-panel__separador">— o —</p>
        {!mostrarCrear ? (
          <button type="button" onClick={() => setMostrarCrear(true)}>
            + Crear jugador
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
            <div className="resource-form__actions">
              <button
                type="button"
                disabled={!puedeCrear || inscribir.isPending}
                onClick={() => inscribir.mutate(nuevoJugador)}
              >
                {inscribir.isPending ? "Validando..." : "Validar e inscribir"}
              </button>
            </div>
          </div>
        )}

        {inscribir.isError && <p className="error-text">{apiErrorMessage(inscribir.error)}</p>}
        {inscritoOk && <p className="success-text">{inscritoOk}</p>}

        <div className="resource-form__actions">
          <button type="button" className="link-button" onClick={onClose}>
            Cerrar
          </button>
        </div>
      </div>
    </div>
  );
}

/** Camino Pareja (Tamano_Equipo == 2) / Conjunto (> 2) — sigue creando un
 * Equipo, sin cambios de fondo respecto al modal original. La única
 * diferencia entre los dos es de UI: Pareja fija la plantilla en
 * exactamente 2 filas (sin "+ agregar fila", la modalidad fija el tamaño)
 * y autonombra el equipo con el nombre completo de ambos jugadores unidos
 * por " / " (Decisión D del plan — nunca solo el apellido, un parser de
 * apellidos se equivoca con nombres compuestos). */
function ModalEquipo(props: {
  torneoId: number;
  torneoContexto: string;
  esPareja: boolean;
  torneoDisciplinaId: number;
  torneoModalidadId: number;
  equiposYaInscritosIds: Set<number>;
  onClose: () => void;
}) {
  const { torneoId, torneoContexto, esPareja, torneoDisciplinaId, torneoModalidadId, equiposYaInscritosIds, onClose } =
    props;
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [modo, setModo] = useState<Modo>({ tipo: "buscar" });
  const [busqueda, setBusqueda] = useState("");
  const [nombreNuevoEquipo, setNombreNuevoEquipo] = useState("");
  const [nombreEditadoAMano, setNombreEditadoAMano] = useState(false);
  const [filas, setFilas] = useState<FilaPlantilla[]>(esPareja ? [{ ...FILA_VACIA }, { ...FILA_VACIA }] : [{ ...FILA_VACIA }]);
  const [inscribiendoId, setInscribiendoId] = useState<number | null>(null);
  // Flujo 3 del plan (Requerimiento 3): resumen de la copia automática de
  // Plantilla Base al roster real, solo se puebla cuando hubo AL MENOS un
  // conflicto — sin conflictos, el éxito es silencioso (mismo criterio
  // que EC-22 del plan anterior, 0 candidatos también es silencioso).
  const [resumenConflictos, setResumenConflictos] = useState<{
    equipoNombre: string;
    insertados: number;
    conflictos: { jugador_perfil_id: number; jugador_nombre: string; mensaje: string }[];
  } | null>(null);

  const catalogo = useCatalogo();
  const nombreDisciplina = catalogo.nombreDisciplina(torneoDisciplinaId);

  // Filtro estricto, del lado del SERVIDOR (pedido B + Mejora #1): solo
  // equipos de la disciplina del torneo y solo Activos.
  //
  // `estado: "Activo"` cierra un bug preexistente (D-Eng-13 / Mejora #3):
  // hasta acá un equipo dado de baja desde /torneo-admin/equipos seguía
  // apareciendo en este picker y se inscribía sin error, porque este
  // filtro solo miraba `equiposYaInscritosIds` y el texto.
  //
  // Que los dos filtros vayan como query params y no en memoria importa
  // por el techo de 200 filas: filtrar después de traer las primeras 200
  // devolvía "no hay resultados" para un equipo que sí existe.
  const equipos = useResourceCrud<EquipoRow>({
    resourceKey: "equipos",
    basePath: "/api/v1/equipos",
    listParams: { disciplina_id: torneoDisciplinaId, estado: "Activo" },
  });

  const equiposDisponibles = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    return (equipos.listQuery.data ?? []).filter(
      (e) => !equiposYaInscritosIds.has(e.id) && (texto === "" || e.nombre.toLowerCase().includes(texto)),
    );
  }, [equipos.listQuery.data, equiposYaInscritosIds, busqueda]);

  // Decisión #9: los equipos de otra disciplina NO se muestran —ni
  // deshabilitados, ni tachados: no son opciones—, pero el silencio total
  // deja al admin sin saber si escribió mal, si el equipo no existe o si
  // es de otra disciplina. Se le da el NÚMERO, nunca los nombres.
  //
  // Esta segunda consulta solo se dispara cuando la búsqueda no encontró
  // nada — que es el único momento en que el número significa algo. D-Eng-14
  // pedía calcularlo sin fetch extra sobre la lista ya cargada; con el
  // filtro por disciplina movido al servidor (que es lo que hace que la
  // búsqueda funcione más allá de 200 filas) esa lista ya no contiene las
  // otras disciplinas, así que el dato hay que pedirlo. Es una llamada
  // rara, en el momento exacto en que el admin necesita la explicación.
  const buscoSinResultados = busqueda.trim() !== "" && equiposDisponibles.length === 0;
  const otrasDisciplinas = useResourceCrud<EquipoRow>({
    resourceKey: "equipos",
    basePath: "/api/v1/equipos",
    listParams: { estado: "Activo" },
    enabled: buscoSinResultados,
  });
  const coincidenEnOtrasDisciplinas = useMemo(() => {
    if (!buscoSinResultados) return 0;
    const texto = busqueda.trim().toLowerCase();
    return (otrasDisciplinas.listQuery.data ?? []).filter(
      (e) => e.disciplina_id !== torneoDisciplinaId && e.nombre.toLowerCase().includes(texto),
    ).length;
  }, [buscoSinResultados, otrasDisciplinas.listQuery.data, busqueda, torneoDisciplinaId]);

  const inscribirExistente = useMutation({
    mutationFn: async (equipo: { id: number; nombre: string }) => {
      const { data, error } = await api.POST("/api/v1/inscripciones", {
        body: { torneo_id: torneoId, equipo_id: equipo.id },
      } as never);
      if (error) throw error;
      return { data, equipoNombre: equipo.nombre };
    },
    onMutate: (equipo) => setInscribiendoId(equipo.id),
    onSuccess: ({ data, equipoNombre }) => {
      queryClient.invalidateQueries({ queryKey: ["inscripciones"] });
      setInscribiendoId(null);
      // Requerimiento 3 / Flujo 3: la inscripción del equipo NUNCA se
      // revierte por un conflicto de jugador — ya se creó. Si hubo
      // alguno, se lo muestra en un modal de confirmación explícita
      // ([Entendido]), no un toast que desaparece solo: puede haber más
      // de un jugador excluido y el admin necesita poder anotarlos.
      const plantillaBase = (data as { plantilla_base?: { insertados: number; conflictos: { jugador_perfil_id: number; jugador_nombre: string; mensaje: string }[] } | null }).plantilla_base;
      if (plantillaBase && plantillaBase.conflictos.length > 0) {
        setResumenConflictos({ equipoNombre, insertados: plantillaBase.insertados, conflictos: plantillaBase.conflictos });
      }
      // Sin conflictos: mismo comportamiento de siempre, el modal de
      // búsqueda queda abierto (el equipo recién inscrito desaparece solo
      // de la lista al refetchear `equiposYaInscritosIds`) — así el admin
      // puede seguir inscribiendo equipos sin reabrir el modal.
    },
    onError: () => setInscribiendoId(null),
  });

  const crearYRegistrar = useMutation({
    mutationFn: async () => {
      // Disciplina y modalidad HEREDADAS del torneo, no elegidas: crear
      // acá un equipo de otra disciplina sería crear uno que este mismo
      // modal no puede inscribir.
      const { data: equipo, error: errEquipo } = await api.POST("/api/v1/equipos", {
        body: {
          nombre: nombreNuevoEquipo.trim(),
          disciplina_id: torneoDisciplinaId,
          modalidad_id: torneoModalidadId,
        },
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
    const nuevasFilas = filas.map((fila, i) => (i === idx ? { ...fila, [campo]: valor } : fila));
    setFilas(nuevasFilas);
    // Decisión D: nombre sugerido = nombre completo de cada jugador, unidos
    // por " / " — nunca solo el apellido (frágil con apellidos compuestos).
    // Se recalcula mientras el admin no haya tocado el campo a mano
    // (EC-28, mismo flag nombreEditadoAMano que ya usaba D-Eng-4 acá).
    if (esPareja && campo === "nombre" && !nombreEditadoAMano) {
      const sugerido = nuevasFilas
        .map((f) => f.nombre.trim())
        .filter((n) => n !== "")
        .join(" / ");
      setNombreNuevoEquipo(sugerido);
    }
  }

  const filasConDato = filas.filter((f) => f.cedula.trim() !== "" || f.nombre.trim() !== "");
  const puedeCrear =
    nombreNuevoEquipo.trim() !== "" &&
    filasConDato.length > 0 &&
    filasConDato.every((f) => f.cedula.trim() && f.nombre.trim() && f.correo_electronico.trim());

  const tituloCrear = esPareja ? "Crear pareja" : "Crear equipo nuevo";
  const botonCrear = esPareja ? "+ Crear pareja nueva" : "+ Crear equipo nuevo";

  return (
    <div className="modal-overlay" role="dialog" aria-label={esPareja ? "Agregar pareja" : "Agregar equipo"}>
      <div className="modal-panel">
        {modo.tipo === "buscar" && (
          <>
            <h2>{esPareja ? "Agregar pareja" : "Agregar equipo"}</h2>
            <input
              aria-label={esPareja ? "Buscar pareja existente" : "Buscar equipo existente"}
              placeholder="Buscar..."
              value={busqueda}
              onChange={(e) => setBusqueda(e.target.value)}
            />
            {equipos.listQuery.isLoading && <p>Cargando...</p>}
            {!equipos.listQuery.isLoading && equiposDisponibles.length === 0 && (
              <p className="muted">
                No hay {esPareja ? "parejas" : "equipos"} de {nombreDisciplina} con ese nombre.
                {coincidenEnOtrasDisciplinas > 0 &&
                  ` ${coincidenEnOtrasDisciplinas} de otras disciplinas coinciden y no se pueden inscribir acá.`}
              </p>
            )}
            {equiposDisponibles.map((e) => (
              <div key={e.id} className="modal-panel__equipo-fila">
                <span>{e.nombre}</span>
                <button
                  type="button"
                  disabled={inscribiendoId === e.id}
                  onClick={() => inscribirExistente.mutate({ id: e.id, nombre: e.nombre })}
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
              {botonCrear}
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
            <h2>
              {tituloCrear} — {torneoContexto}
            </h2>
            {/* Heredada del torneo: texto plano, no un <select disabled>
                — un select deshabilitado sigue pareciendo un campo de
                formulario roto (mismo criterio que "Nueva edición"). */}
            <dl className="datos-heredados">
              <div>
                <dt>Disciplina</dt>
                <dd>{nombreDisciplina}</dd>
              </div>
            </dl>
            <div className="resource-form">
              <label>
                Nombre {esPareja ? "de la pareja" : "del equipo"}
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
            {/* Pareja: exactamente 2 filas, la modalidad fija el tamaño —
                mismo criterio que ya ocultaba este botón para Individual. */}
            {!esPareja && (
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

      {resumenConflictos && (
        <div className="modal-overlay" role="dialog" aria-label="Conflictos de plantilla base">
          <div className="modal-panel">
            <p>
              Equipo inscrito. {resumenConflictos.insertados} jugador{resumenConflictos.insertados === 1 ? "" : "es"}{" "}
              agregado{resumenConflictos.insertados === 1 ? "" : "s"}.
            </p>
            <p>⚠️ Alerta crítica:</p>
            {resumenConflictos.conflictos.map((c) => (
              <p key={c.jugador_perfil_id}>
                {c.jugador_nombre} — {c.mensaje}
              </p>
            ))}
            <div className="resource-form__actions">
              <button type="button" onClick={() => setResumenConflictos(null)}>
                Entendido
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
