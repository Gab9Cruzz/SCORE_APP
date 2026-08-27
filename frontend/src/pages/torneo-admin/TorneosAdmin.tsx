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
  modalidad_id: number | null;
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
  tipo: string;
}
interface ModalidadRow {
  id: number;
  nombre: string;
  disciplina_id: number;
}
interface TorneoCreatePayload {
  disciplina_id: number;
  modalidad_id: number | null;
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

  /** Modalidad condicional (torneos-admin-plan.md, Fase 2, sección A): solo
   * se muestra si la Disciplina elegida es de Tipo="Individual", y sus
   * opciones se filtran a las de esa disciplina. `incluirNombreGrupo`
   * distingue "Torneo nuevo" (pide el nombre del grupo) de "Nueva edición
   * de {grupo}" (el grupo ya está fijo, no se vuelve a pedir). */
  function camposTorneo(incluirNombreGrupo: boolean) {
    return (values: Record<string, ResourceFieldValue>): ResourceFormField[] => {
      const disciplinaId = values.disciplina_id as number | null;
      const disciplina = disciplinaId != null ? disciplinaPorId.get(disciplinaId) : undefined;
      const campos: ResourceFormField[] = [];
      if (incluirNombreGrupo) {
        campos.push({ name: "torneo_grupo_nombre", label: "Nombre del torneo", type: "text", required: true });
      }
      campos.push({
        name: "disciplina_id",
        label: "Disciplina",
        type: "reference",
        required: true,
        optionsLoading: disciplinas.listQuery.isLoading,
        options: (disciplinas.listQuery.data ?? []).map((d) => ({ value: d.id, label: d.nombre })),
      });
      if (disciplina?.tipo === "Individual") {
        campos.push({
          name: "modalidad_id",
          label: "Modalidad",
          type: "reference",
          required: true,
          optionsLoading: modalidades.listQuery.isLoading,
          options: (modalidades.listQuery.data ?? [])
            .filter((m) => m.disciplina_id === disciplinaId)
            .map((m) => ({ value: m.id, label: m.nombre })),
        });
      }
      campos.push({ name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true });
      campos.push({ name: "fecha_fin", label: "Fecha de fin", type: "date", required: true });
      return campos;
    };
  }

  function submitCrearGrupo(values: Record<string, ResourceFieldValue>) {
    crearTorneo.mutate({
      torneo_grupo_nombre: String(values.torneo_grupo_nombre ?? ""),
      disciplina_id: values.disciplina_id as number,
      modalidad_id: (values.modalidad_id as number | null) ?? null,
      fecha_inicio: String(values.fecha_inicio),
      fecha_fin: String(values.fecha_fin),
    });
  }

  function submitNuevaEdicion(grupoId: number, values: Record<string, ResourceFieldValue>) {
    crearTorneo.mutate({
      torneo_grupo_id: grupoId,
      disciplina_id: values.disciplina_id as number,
      modalidad_id: (values.modalidad_id as number | null) ?? null,
      fecha_inicio: String(values.fecha_inicio),
      fecha_fin: String(values.fecha_fin),
    });
  }

  if (modo.tipo === "crear-grupo") {
    return (
      <div className="page">
        <h1>Torneo nuevo</h1>
        <ResourceForm
          fields={camposTorneo(true)}
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
    return (
      <div className="page">
        <h1>
          Nueva edición — {modo.grupo.nombre} (Edición {siguienteNumero})
        </h1>
        <ResourceForm
          fields={camposTorneo(false)}
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
