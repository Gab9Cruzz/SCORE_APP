import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api, apiErrorMessage } from "../../api/client";
import { ResourceForm, type ResourceFieldValue, type ResourceFormField } from "../../components/admin/ResourceForm";
import { useResourceCrud } from "../../hooks/useResourceCrud";

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
interface DisciplinaRow {
  id: number;
  nombre: string;
}
interface ModalidadRow {
  id: number;
  nombre: string;
  disciplina_id: number;
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

  const gruposQuery = useQuery({
    queryKey: ["torneo-grupos"],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/torneo-grupos", {});
      if (error) throw error;
      return data as TorneoGrupo[];
    },
  });

  const disciplinas = useResourceCrud<DisciplinaRow>({ resourceKey: "disciplinas", basePath: "/api/v1/disciplinas" });
  const modalidades = useResourceCrud<ModalidadRow>({ resourceKey: "modalidades", basePath: "/api/v1/modalidades" });

  const disciplinaPorId = useMemo(
    () => new Map((disciplinas.listQuery.data ?? []).map((d) => [d.id, d])),
    [disciplinas.listQuery.data],
  );
  const modalidadPorId = useMemo(
    () => new Map((modalidades.listQuery.data ?? []).map((m) => [m.id, m])),
    [modalidades.listQuery.data],
  );

  const crearTorneo = useMutation({
    mutationFn: async (body: TorneoCreatePayload) => {
      const { data, error } = await api.POST("/api/v1/torneos", { body } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["torneo-grupos"] });
      setModo({ tipo: "lista" });
    },
  });

  function volver() {
    setModo({ tipo: "lista" });
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
    return [
      { name: "torneo_grupo_nombre", label: "Nombre del torneo", type: "text", required: true },
      {
        name: "disciplina_id",
        label: "Disciplina",
        type: "reference",
        required: true,
        optionsLoading: disciplinas.listQuery.isLoading,
        options: (disciplinas.listQuery.data ?? []).map((d) => ({ value: d.id, label: d.nombre })),
      },
      {
        name: "modalidad_id",
        label: "Modalidad",
        type: "reference",
        required: true,
        optionsLoading: modalidades.listQuery.isLoading,
        options: (modalidades.listQuery.data ?? [])
          .filter((m) => m.disciplina_id === disciplinaId)
          .map((m) => ({ value: m.id, label: m.nombre })),
      },
      { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
      { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
    ];
  }

  const camposNuevaEdicion: ResourceFormField[] = [
    { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
    { name: "fecha_fin", label: "Fecha de fin", type: "date", required: true },
  ];

  function submitCrearGrupo(values: Record<string, ResourceFieldValue>) {
    crearTorneo.mutate({
      torneo_grupo_nombre: String(values.torneo_grupo_nombre ?? ""),
      disciplina_id: values.disciplina_id as number,
      modalidad_id: values.modalidad_id as number,
      fecha_inicio: String(values.fecha_inicio),
      fecha_fin: String(values.fecha_fin),
    });
  }

  function submitNuevaEdicion(grupoId: number, values: Record<string, ResourceFieldValue>) {
    // Sin disciplina_id/modalidad_id: se heredan del grupo del lado del
    // backend (D-Eng-5) — este formulario ni siquiera los pide.
    crearTorneo.mutate({
      torneo_grupo_id: grupoId,
      fecha_inicio: String(values.fecha_inicio),
      fecha_fin: String(values.fecha_fin),
    });
  }

  if (modo.tipo === "crear-grupo") {
    return (
      <div className="page">
        <h1>Torneo nuevo</h1>
        <ResourceForm
          fields={camposTorneoNuevo}
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
    const disciplinaHeredada = disciplinaPorId.get(edicionReferencia?.disciplina_id);
    const modalidadHeredada = modalidadPorId.get(edicionReferencia?.modalidad_id ?? -1);
    return (
      <div className="page">
        <h1>
          Nueva edición — {modo.grupo.nombre} (Edición {siguienteNumero})
        </h1>
        <dl className="datos-heredados">
          <div>
            <dt>Disciplina</dt>
            <dd>{disciplinaHeredada?.nombre ?? "…"}</dd>
          </div>
          <div>
            <dt>Modalidad</dt>
            <dd>{modalidadHeredada?.nombre ?? "…"}</dd>
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
        <h1>Torneos</h1>
        <button type="button" onClick={() => setModo({ tipo: "crear-grupo" })}>
          + Torneo nuevo
        </button>
      </div>
      {gruposQuery.isLoading && <p>Cargando...</p>}
      {gruposQuery.isError && <p className="error-text">{apiErrorMessage(gruposQuery.error)}</p>}
      {gruposQuery.data?.length === 0 && <p className="muted">No hay torneos creados todavía.</p>}
      <div className="tarjetas-torneos">
        {gruposQuery.data?.map((grupo) => {
          const edicion = edicionParaAbrir(grupo);
          const disciplina = disciplinaPorId.get(edicion?.disciplina_id);
          return (
            <div key={grupo.id} className="tarjeta-torneo">
              <h2>{grupo.nombre}</h2>
              <p className="muted">
                {disciplina?.nombre ?? "…"}
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
