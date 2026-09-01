import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { ResourceForm, type ResourceFieldValue, type ResourceFormField } from "../../components/admin/ResourceForm";
import { useCatalogo } from "../../hooks/useCatalogo";
import { FiltroDisciplinasBar } from "./FiltroDisciplinasBar";

interface EdicionResumen {
  id: number;
  numero_edicion: number;
  disciplina_id: number;
  modalidad_id: number;
  estado: string;
  fecha_inicio: string;
  fecha_fin: string;
}
interface TorneoGrupo {
  id: number;
  nombre: string;
  ediciones: EdicionResumen[];
}
interface TorneoCreatePayload {
  // Ambos opcionales en el payload (ediciones-catalogo-disciplinas-plan.md,
  // D-Eng-5): obligatorios al crear un grupo nuevo, omitidos en una nueva
  // edición — el backend los ignora igual si vinieran, pero no tiene
  // sentido mandar un dato que ni siquiera se le pide al admin.
  disciplina_id?: number;
  modalidad_id?: number;
  fecha_inicio: string;
  fecha_fin: string;
  torneo_grupo_id?: number;
  torneo_grupo_nombre?: string;
  // Motor de Formatos (motor-formatos-plantillas-navegacion-plan.md) —
  // solo se mandan al crear un grupo nuevo, igual que disciplina/modalidad
  // (una "Nueva edición" hereda el Formato del grupo, D-Eng-5 extendido).
  formato?: "Liga" | "Eliminacion" | "Grupos_Playoffs";
  ida_vuelta?: boolean;
  incluye_tercer_lugar?: boolean;
  equipos_por_grupo?: number;
  clasificados_por_grupo?: number;
  // Motor de Tiempos (gestion-avanzada-equipos-control-mesa-plan.md) —
  // igual que Formato: solo se manda al crear un grupo nuevo (una "Nueva
  // edición" no la pide, TorneoService la conserva de la edición
  // anterior si no viene). Si se omite, el backend aplica un default
  // derivado de Modalidad.tamano_equipo.
  config_tiempo?: {
    tipo_cronometro: "Periodos" | "Corrido";
    cantidad_periodos?: number;
    duracion_periodo_minutos?: number;
    duracion_descanso_minutos?: number;
  };
}

const formatearFecha = (iso: string) => new Date(iso).toLocaleDateString("es-AR");

type Modo = { tipo: "lista" } | { tipo: "crear-grupo" } | { tipo: "nueva-edicion"; grupo: TorneoGrupo };

/** La edición que abre "Ver Torneo": la Activa más reciente si hay una, o
 * la de numero_edicion más alto si no (las ediciones ya vienen ordenadas
 * desc por numero_edicion desde el backend — ver TorneoRepository.listar_ediciones_del_grupo).
 * "Activa" pesa más que "más reciente" a propósito: una Edición 3 recién
 * creada pero con fecha_inicio futura no debería tapar a una Edición 2
 * que sigue jugándose. */
function edicionParaAbrir(grupo: TorneoGrupo): EdicionResumen {
  return grupo.ediciones.find((e) => e.estado === "Activo") ?? grupo.ediciones[0];
}

export function TorneosAdminPage() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });
  // Precargado desde la URL cuando se llega desde la grilla de Equipos
  // ("agregar plantilla" de un equipo sin inscribir manda su disciplina) —
  // el admin cae en la barra ya filtrada por lo que estaba mirando. El
  // filtro NO se persiste de vuelta en la URL: eso es alcance nuevo (ver
  // "NOT en scope" del plan), esto solo lee un parámetro de entrada.
  const [searchParams] = useSearchParams();
  const disciplinaInicial = searchParams.get("disciplina_id");
  const [disciplinaFiltro, setDisciplinaFiltro] = useState<number | null>(
    disciplinaInicial ? Number(disciplinaInicial) : null,
  );
  const [modalidadFiltro, setModalidadFiltro] = useState<number | null>(null);

  const gruposQuery = useQuery({
    queryKey: ["torneo-grupos"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneo-grupos", {});
      if (error) throw error;
      return data as TorneoGrupo[];
    },
  });

  const catalogo = useCatalogo();

  const grupos = useMemo(() => gruposQuery.data ?? [], [gruposQuery.data]);

  /** La disciplina/modalidad de un grupo son las de la edición que se
   * abriría — un grupo no cambia de disciplina entre ediciones (el
   * backend las hereda, D-Eng-5), así que alcanza con mirar una. */
  const disciplinaDeGrupo = (g: TorneoGrupo) => edicionParaAbrir(g)?.disciplina_id ?? null;
  const modalidadDeGrupo = (g: TorneoGrupo) => edicionParaAbrir(g)?.modalidad_id ?? null;

  // D-Eng-16: los chips salen de los torneos YA cargados, sin endpoint ni
  // llamada extra. Eso garantiza por construcción que ningún chip filtre a
  // vacío, y evita una barra de 28 disciplinas cuando hay torneos de 4.
  const { disciplinaPorId, modalidadPorId } = catalogo;
  const chipsDisciplina = useMemo(() => {
    const ids = new Set(grupos.map(disciplinaDeGrupo).filter((id): id is number => id != null));
    return [...ids]
      .map((id) => ({
        id,
        nombre: disciplinaPorId.get(id)?.nombre ?? "—",
        ordenPopularidad: disciplinaPorId.get(id)?.orden_popularidad ?? null,
      }))
      // Barra tipo SofaScore ordenada por popularidad, no alfabético
      // (motor-formatos-plantillas-navegacion-plan.md, #3) — sigue
      // mostrando solo disciplinas con torneos (D-Eng-16, sin cambios),
      // la popularidad decide el ORDEN entre las que aparecen.
      .sort((a, b) => (a.ordenPopularidad ?? 999) - (b.ordenPopularidad ?? 999));
  }, [grupos, disciplinaPorId]);

  const chipsModalidad = useMemo(() => {
    if (disciplinaFiltro === null) return [];
    const ids = new Set(
      grupos
        .filter((g) => disciplinaDeGrupo(g) === disciplinaFiltro)
        .map(modalidadDeGrupo)
        .filter((id): id is number => id != null),
    );
    return [...ids]
      .map((id) => ({ id, nombre: modalidadPorId.get(id)?.nombre ?? "—" }))
      .sort((a, b) => a.nombre.localeCompare(b.nombre));
  }, [grupos, disciplinaFiltro, modalidadPorId]);

  const gruposVisibles = useMemo(
    () =>
      grupos.filter((g) => {
        if (disciplinaFiltro !== null && disciplinaDeGrupo(g) !== disciplinaFiltro) return false;
        if (modalidadFiltro !== null && modalidadDeGrupo(g) !== modalidadFiltro) return false;
        return true;
      }),
    [grupos, disciplinaFiltro, modalidadFiltro],
  );

  const hayFiltro = disciplinaFiltro !== null || modalidadFiltro !== null;

  const crearTorneo = useMutation({
    mutationFn: async (body: TorneoCreatePayload) => {
      const { data, error } = await api.POST("/api/v1/torneos", { body } as never);
      if (error) throw error;
      return data as { id: number; disciplina_id: number };
    },
  });

  function volver() {
    setModo({ tipo: "lista" });
  }

  function seleccionarDisciplina(id: number | null) {
    setDisciplinaFiltro(id);
    // La modalidad elegida pertenece a la disciplina anterior: dejarla
    // puesta filtraría a vacío por construcción.
    setModalidadFiltro(null);
  }

  /** Campos del formulario de "Torneo nuevo" (crea un TORNEO_GRUPO):
   * Disciplina y Modalidad son siempre obligatorias (catálogo unificado —
   * ediciones-catalogo-disciplinas-plan.md, Decisión A1: toda disciplina
   * tiene 1+ modalidades, ya no hay un Tipo="Equipo" que las omita). Las
   * opciones de Modalidad se filtran a las de la Disciplina elegida — sin
   * disciplina elegida todavía, el select de Modalidad queda vacío.
   *
   * "Nueva edición" de un grupo YA existente NO usa esta función — ver
   * el bloque `modo.tipo === "nueva-edicion"` más abajo: Disciplina y
   * Modalidad se muestran como texto heredado, no como campos del form
   * (Fase 2 parte A del plan; D-Eng-5 hace que el backend las ignore igual
   * si se mandaran). */
  function camposTorneoNuevo(values: Record<string, ResourceFieldValue>): ResourceFormField[] {
    const disciplinaId = values.disciplina_id as number | null;
    // Motor de Formatos (Design sección E, motor-formatos-plantillas-
    // navegacion-plan.md): Formato decide qué parámetros aplican — el
    // selector nunca muestra un campo que el Formato elegido no usa, y el
    // backend (TorneoService._validar_parametros_formato) rechaza igual
    // cualquiera que llegara de otra forma.
    const formato = (values.formato as string | null) ?? "Liga";
    // Motor de Tiempos (gestion-avanzada-equipos-control-mesa-plan.md,
    // sección "Configuración de tiempos"): Tipo_Cronometro es explícito
    // por torneo, no derivado rígido de la disciplina (el mismo deporte
    // puede jugarse 2x45' o 2x20' según el nivel) — pero el default que
    // preselecciona el formulario SÍ sigue a Modalidad.tamano_equipo, acá
    // vía initialValues (ver más abajo) porque ResourceForm no soporta
    // recalcular un default a mitad de edición sin pisar lo que el admin
    // ya haya tocado.
    const tipoCronometro = (values.tipo_cronometro as string | null) ?? "Periodos";
    return [
      { name: "torneo_grupo_nombre", label: "Nombre del torneo", type: "text", required: true },
      {
        name: "disciplina_id",
        label: "Disciplina",
        type: "reference",
        required: true,
        optionsLoading: catalogo.cargando,
        options: catalogo.disciplinas.map((d) => ({ value: d.id, label: d.nombre })),
      },
      {
        name: "modalidad_id",
        label: "Modalidad",
        type: "reference",
        required: true,
        optionsLoading: catalogo.cargando,
        options: catalogo.modalidadesDe(disciplinaId).map((m) => ({ value: m.id, label: m.nombre })),
      },
      {
        name: "formato",
        label: "Formato",
        type: "select",
        required: true,
        choices: ["Liga", "Eliminacion", "Grupos_Playoffs"],
      },
      ...(formato === "Liga"
        ? ([{ name: "ida_vuelta", label: "Ida y vuelta", type: "checkbox" }] as ResourceFormField[])
        : []),
      ...(formato !== "Liga"
        ? ([{ name: "incluye_tercer_lugar", label: "Jugar partido por el 3er lugar", type: "checkbox" }] as ResourceFormField[])
        : []),
      ...(formato === "Grupos_Playoffs"
        ? ([
            { name: "equipos_por_grupo", label: "Equipos por grupo", type: "number" },
            { name: "clasificados_por_grupo", label: "Clasifican por grupo", type: "number" },
          ] as ResourceFormField[])
        : []),
      { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
      { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
      {
        name: "tipo_cronometro",
        label: "Cronómetro",
        type: "select",
        required: true,
        choices: ["Periodos", "Corrido"],
      },
      ...(tipoCronometro === "Periodos"
        ? ([
            { name: "cantidad_periodos", label: "Cantidad de períodos", type: "number", required: true },
            { name: "duracion_periodo_minutos", label: "Duración de cada período (min)", type: "number", required: true },
            { name: "duracion_descanso_minutos", label: "Duración del descanso (min, opcional)", type: "number" },
          ] as ResourceFormField[])
        : []),
    ];
  }

  const camposNuevaEdicion: ResourceFormField[] = [
    { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
    { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
  ];

  function submitCrearGrupo(values: Record<string, ResourceFieldValue>) {
    const disciplinaId = values.disciplina_id as number;
    const formato = (values.formato as "Liga" | "Eliminacion" | "Grupos_Playoffs" | null) ?? "Liga";
    const tipoCronometro = (values.tipo_cronometro as "Periodos" | "Corrido" | null) ?? "Periodos";
    crearTorneo.mutate(
      {
        torneo_grupo_nombre: String(values.torneo_grupo_nombre ?? ""),
        disciplina_id: disciplinaId,
        modalidad_id: values.modalidad_id as number,
        fecha_inicio: String(values.fecha_inicio),
        fecha_fin: String(values.fecha_fin),
        formato,
        ida_vuelta: formato === "Liga" ? Boolean(values.ida_vuelta) : undefined,
        incluye_tercer_lugar: formato !== "Liga" ? Boolean(values.incluye_tercer_lugar) : undefined,
        equipos_por_grupo:
          formato === "Grupos_Playoffs" && values.equipos_por_grupo ? Number(values.equipos_por_grupo) : undefined,
        clasificados_por_grupo:
          formato === "Grupos_Playoffs" && values.clasificados_por_grupo
            ? Number(values.clasificados_por_grupo)
            : undefined,
        config_tiempo:
          tipoCronometro === "Periodos"
            ? {
                tipo_cronometro: "Periodos",
                cantidad_periodos: Number(values.cantidad_periodos ?? 2),
                duracion_periodo_minutos: Number(values.duracion_periodo_minutos ?? 45),
                duracion_descanso_minutos: values.duracion_descanso_minutos
                  ? Number(values.duracion_descanso_minutos)
                  : undefined,
              }
            : { tipo_cronometro: "Corrido" },
      },
      {
        // EC-46 (motor-formatos-plantillas-navegacion-plan.md): mismo
        // onSuccess que submitNuevaEdicion — crear un torneo la PRIMERA
        // vez (grupo nuevo) usa la misma mutación crearTorneo, que
        // devuelve el TORNEO con .id en los dos casos, así que cae
        // directo en "Agregar Equipo" igual que la rama de Nueva Edición.
        onSuccess: (nuevoTorneo) => {
          queryClient.invalidateQueries({ queryKey: ["torneo-grupos"] });
          // EC-42: si la barra estaba filtrada por otra disciplina, el
          // torneo recién creado no aparecería y el admin creería que
          // falló. Se resetea el filtro en vez de dejarlo escondido.
          if (disciplinaFiltro !== null && disciplinaFiltro !== disciplinaId) {
            seleccionarDisciplina(null);
          }
          setModo({ tipo: "lista" });
          navigate(`/torneo-admin/torneos/${nuevoTorneo.id}/equipos`);
        },
      },
    );
  }

  function submitNuevaEdicion(grupoId: number, values: Record<string, ResourceFieldValue>) {
    // Sin disciplina_id/modalidad_id: se heredan del grupo del lado del
    // backend (D-Eng-5) — este formulario ni siquiera los pide.
    crearTorneo.mutate(
      {
        torneo_grupo_id: grupoId,
        fecha_inicio: String(values.fecha_inicio),
        fecha_fin: String(values.fecha_fin),
      },
      {
        // Pedido C del plan: caer DIRECTO en "Agregar Equipo" de la
        // edición recién creada. Antes este onSuccess volvía al listado y
        // dejaba al admin frente a una tarjeta más, sin nada que hacer con
        // ella. (El mismo botón dentro de "Ver Torneo" —
        // TorneoDashboard.crearEdicion — ya navegaba bien; acá estaba el
        // camino roto.) La disciplina va heredada, así que la validación
        // del picker de equipos ya llega puesta.
        onSuccess: (nuevaEdicion) => {
          queryClient.invalidateQueries({ queryKey: ["torneo-grupos"] });
          setModo({ tipo: "lista" });
          navigate(`/torneo-admin/torneos/${nuevaEdicion.id}/equipos`);
        },
      },
    );
  }

  if (modo.tipo === "crear-grupo") {
    return (
      <div className="page">
        <h1>Torneo nuevo</h1>
        <ResourceForm
          fields={camposTorneoNuevo}
          initialValues={{
            formato: "Liga",
            incluye_tercer_lugar: true,
            // Default razonable (deporte de equipo, fútbol 2x45') — el
            // admin lo cambia si eligió una disciplina individual o un
            // formato distinto. Un default que siguiera la Modalidad
            // elegida en vivo no es posible acá: ResourceForm fija
            // initialValues una sola vez al montar (no puede pisar lo que
            // el admin ya tocó cada vez que cambia de disciplina).
            tipo_cronometro: "Periodos",
            cantidad_periodos: 2,
            duracion_periodo_minutos: 45,
            duracion_descanso_minutos: 15,
          }}
          onSubmit={submitCrearGrupo}
          submitting={crearTorneo.isPending}
          submitError={crearTorneo.isError ? apiErrorMessage(crearTorneo.error) : null}
          submitLabel="Crear"
          onCancel={volver}
        />
      </div>
    );
  }

  if (modo.tipo === "nueva-edicion") {
    const siguienteNumero = Math.max(...modo.grupo.ediciones.map((e) => e.numero_edicion)) + 1;
    // Heredados de la edición más reciente del grupo (mismo criterio que
    // TorneoService.create del lado del backend, D-Eng-5) — se muestran
    // como texto plano, no un <select disabled>: un select deshabilitado
    // sigue pareciendo un campo de formulario y el admin puede
    // preguntarse por qué no responde (Fase 2 parte A del plan).
    const edicionReferencia = edicionParaAbrir(modo.grupo);
    return (
      <div className="page">
        <h1>
          Nueva edición — {modo.grupo.nombre} (Edición {siguienteNumero})
        </h1>
        <dl className="datos-heredados">
          <div>
            <dt>Disciplina</dt>
            <dd>{catalogo.nombreDisciplina(edicionReferencia?.disciplina_id)}</dd>
          </div>
          <div>
            <dt>Modalidad</dt>
            <dd>{catalogo.nombreModalidad(edicionReferencia?.modalidad_id)}</dd>
          </div>
        </dl>
        <ResourceForm
          fields={camposNuevaEdicion}
          onSubmit={(values) => submitNuevaEdicion(modo.grupo.id, values)}
          submitting={crearTorneo.isPending}
          submitError={crearTorneo.isError ? apiErrorMessage(crearTorneo.error) : null}
          submitLabel="Crear edición"
          onCancel={volver}
        />
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__header">
        <h1>
          Torneos{" "}
          {hayFiltro && (
            <span className="muted contador-filtrado">
              ({gruposVisibles.length} de {grupos.length})
            </span>
          )}
        </h1>
        <button type="button" onClick={() => setModo({ tipo: "crear-grupo" })}>
          + Torneo nuevo
        </button>
      </div>

      {/* Sin torneos la barra no se renderiza: una barra de filtros sobre
          cero resultados es ruido, no navegación. */}
      {grupos.length > 0 && (
        <FiltroDisciplinasBar
          disciplinas={chipsDisciplina}
          modalidades={chipsModalidad}
          disciplinaSeleccionada={disciplinaFiltro}
          modalidadSeleccionada={modalidadFiltro}
          onSeleccionarDisciplina={seleccionarDisciplina}
          onSeleccionarModalidad={setModalidadFiltro}
        />
      )}

      {gruposQuery.isLoading && <p>Cargando...</p>}
      {gruposQuery.isError && <p className="error-text">{apiErrorMessage(gruposQuery.error)}</p>}
      {grupos.length === 0 && !gruposQuery.isLoading && (
        <p className="muted">No hay torneos creados todavía.</p>
      )}
      {/* Vacío FILTRADO — distinto del vacío real. Imposible por
          construcción (los chips salen de estos mismos torneos), pero el
          estado puede desincronizarse tras crear o dar de baja uno. */}
      {grupos.length > 0 && gruposVisibles.length === 0 && (
        <p className="muted">
          Ningún torneo de {catalogo.nombreDisciplina(disciplinaFiltro)}.{" "}
          <button type="button" className="link-button" onClick={() => seleccionarDisciplina(null)}>
            Ver todos
          </button>
        </p>
      )}

      <div className="tarjetas-torneos">
        {gruposVisibles.map((grupo) => {
          const edicion = edicionParaAbrir(grupo);
          return (
            <div key={grupo.id} className="tarjeta-torneo">
              <h2>{grupo.nombre}</h2>
              <p className="muted">
                {catalogo.nombreDisciplina(edicion?.disciplina_id)}
                {grupo.ediciones.length > 1 && ` · ${grupo.ediciones.length} ediciones`}
              </p>
              {edicion && (
                <p className="muted">
                  Edición {edicion.numero_edicion} — {edicion.estado} ({formatearFecha(edicion.fecha_inicio)} a{" "}
                  {formatearFecha(edicion.fecha_fin)})
                </p>
              )}
              <div className="tarjeta-torneo__acciones">
                <button type="button" onClick={() => setModo({ tipo: "nueva-edicion", grupo })}>
                  + Nueva edición
                </button>
                <button
                  type="button"
                  disabled={!edicion}
                  onClick={() => edicion && navigate(`/torneo-admin/torneos/${edicion.id}`)}
                >
                  Ver Torneo →
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
