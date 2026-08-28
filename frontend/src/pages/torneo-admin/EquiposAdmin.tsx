import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiErrorMessage } from "../../api/client";
import { FiltrosRecurso } from "../../components/admin/FiltrosRecurso";
import { ResourceForm, type ResourceFieldValue, type ResourceFormField } from "../../components/admin/ResourceForm";
import { ResourceTable, type ResourceTableColumn } from "../../components/admin/ResourceTable";
import { useCatalogo } from "../../hooks/useCatalogo";
import { LIMITE_LISTA, useResourceCrud } from "../../hooks/useResourceCrud";
import { iconoDisciplina } from "./iconosDisciplina";

interface EquipoRow {
  id: number;
  nombre: string;
  disciplina_id: number;
  modalidad_id: number;
  plantilla_total: number;
  estado: string;
}

type Modo = { tipo: "lista" } | { tipo: "crear" } | { tipo: "editar"; fila: EquipoRow };

/** Módulo de Gestión de Equipos (equipos-disciplina-navegacion-plan.md,
 * pedido A). Sale de `SimpleResourceAdminPage` —que sirve para un recurso
 * de columnas planas y un formulario fijo— porque acá hacen falta las dos
 * cosas que esa página no soporta: columnas CALCULADAS (Disciplina y
 * Categoría son nombres que hay que cruzar contra el catálogo, Plantilla
 * es un conteo que además es un link) y un formulario con un campo
 * DEPENDIENTE de otro (Modalidad se filtra por la Disciplina elegida).
 *
 * La composición es la que pide el plan para poder crecer: filtros +
 * tabla + formulario, cada uno un componente aparte, y las columnas como
 * un array de configuración. Agregar "Partidos jugados" mañana es una
 * entrada más en `columnas` + un campo más en `EquipoOut`, no una
 * refactorización. */
export function EquiposAdminPage() {
  const navigate = useNavigate();
  const catalogo = useCatalogo();
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });

  const [disciplinaFiltro, setDisciplinaFiltro] = useState("");
  const [modalidadFiltro, setModalidadFiltro] = useState("");
  const [estadoFiltro, setEstadoFiltro] = useState("");
  const [busqueda, setBusqueda] = useState("");

  // Disciplina/Modalidad/Estado se filtran EN EL SERVIDOR (Mejora #1): son
  // los que sacan a la grilla del techo de 200 filas. La búsqueda por
  // texto sigue siendo en memoria — no hay `?nombre=` en la API y
  // agregarlo es alcance nuevo; el banner de truncado avisa cuando eso
  // deja de alcanzar.
  const listParams = useMemo(() => {
    const params: Record<string, unknown> = {};
    if (disciplinaFiltro) params.disciplina_id = Number(disciplinaFiltro);
    if (modalidadFiltro) params.modalidad_id = Number(modalidadFiltro);
    if (estadoFiltro) params.estado = estadoFiltro;
    return params;
  }, [disciplinaFiltro, modalidadFiltro, estadoFiltro]);

  const crud = useResourceCrud<EquipoRow>({
    resourceKey: "equipos",
    basePath: "/api/v1/equipos",
    listParams,
  });

  const equipos = useMemo(() => crud.listQuery.data ?? [], [crud.listQuery.data]);

  const filas = useMemo(() => {
    const texto = busqueda.trim().toLowerCase();
    if (texto === "") return equipos;
    return equipos.filter((e) => e.nombre.toLowerCase().includes(texto));
  }, [equipos, busqueda]);

  const hayFiltros = Boolean(disciplinaFiltro || modalidadFiltro || estadoFiltro || busqueda.trim());

  function limpiarFiltros() {
    setDisciplinaFiltro("");
    setModalidadFiltro("");
    setEstadoFiltro("");
    setBusqueda("");
  }

  function volver() {
    setModo({ tipo: "lista" });
  }

  /** Camino 2 del plan (Fase 2 parte B): desde el catálogo global NO hay
   * torneo, así que no hay dónde colgar una plantilla (Decisión #1 = A1).
   * En vez de pedir jugadores que no se podrían guardar, el equipo se
   * crea y el admin sale derecho al listado de torneos —ya filtrado por
   * su disciplina— para inscribirlo y cargar la plantilla ahí, que es
   * donde ese flujo ya está construido. */
  function irAInscribir(disciplinaId: number) {
    navigate(`/torneo-admin/torneos?disciplina_id=${disciplinaId}`);
  }

  const camposEquipo = (values: Record<string, ResourceFieldValue>): ResourceFormField[] => {
    const disciplinaId = values.disciplina_id as number | null;
    return [
      { name: "nombre", label: "Nombre", type: "text", required: true },
      {
        name: "disciplina_id",
        label: "Disciplina",
        type: "reference",
        required: true,
        optionsLoading: catalogo.cargando,
        options: catalogo.disciplinas.map((d) => ({ value: d.id, label: d.nombre })),
      },
      {
        // "Categoría" es la Modalidad del equipo (Decisión #2 = B1). Se
        // etiqueta "Categoría" en la grilla porque es como el admin la
        // pidió, y "Modalidad" acá porque es el nombre del catálogo que
        // está eligiendo — el mismo criterio que ya usa TorneosAdmin.
        name: "modalidad_id",
        label: "Categoría (modalidad)",
        type: "reference",
        required: true,
        optionsLoading: catalogo.cargando,
        options: catalogo.modalidadesDe(disciplinaId).map((m) => ({ value: m.id, label: m.nombre })),
      },
    ];
  };

  const columnas: ResourceTableColumn<EquipoRow>[] = [
    { key: "nombre", label: "Nombre" },
    {
      key: "disciplina",
      label: "Disciplina",
      render: (r) => {
        const nombre = catalogo.nombreDisciplina(r.disciplina_id);
        const emoji = iconoDisciplina(nombre);
        return emoji ? `${emoji} ${nombre}` : nombre;
      },
    },
    { key: "categoria", label: "Categoría", render: (r) => catalogo.nombreModalidad(r.modalidad_id) },
    {
      key: "plantilla",
      label: "Plantilla",
      // EC-39: 0 jugadores es un estado VÁLIDO, no un error — pero el
      // vacío tiene que ofrecer la salida, no solo informarla. Con 0, el
      // conteo es el link a inscribir el equipo (que es donde se carga la
      // plantilla); con más, es texto plano.
      render: (r) =>
        r.plantilla_total === 0 ? (
          <button type="button" className="link-button" onClick={() => irAInscribir(r.disciplina_id)}>
            0 jug. — agregar
          </button>
        ) : (
          `${r.plantilla_total} jug.`
        ),
    },
    { key: "estado", label: "Estado" },
  ];

  if (modo.tipo === "crear" || modo.tipo === "editar") {
    const editando = modo.tipo === "editar";
    const initialValues = editando
      ? {
          nombre: modo.fila.nombre,
          disciplina_id: modo.fila.disciplina_id,
          modalidad_id: modo.fila.modalidad_id,
          estado: modo.fila.estado,
        }
      : undefined;
    const campos = editando
      ? (values: Record<string, ResourceFieldValue>): ResourceFormField[] => [
          ...camposEquipo(values),
          { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo"] },
        ]
      : camposEquipo;
    const mutation = editando ? crud.update : crud.create;

    return (
      <div className="page">
        <h1>{editando ? "Editar" : "Nuevo"} — Equipos</h1>
        <ResourceForm
          fields={campos}
          initialValues={initialValues}
          onSubmit={(values) =>
            editando
              ? crud.update.mutate({ id: modo.fila.id, body: values as never }, { onSuccess: volver })
              : crud.create.mutate(values as never, { onSuccess: volver })
          }
          submitting={mutation.isPending}
          submitError={mutation.isError ? apiErrorMessage(mutation.error) : null}
          submitLabel={editando ? "Guardar cambios" : "Crear"}
          onCancel={volver}
        />
        {!editando && (
          // El pedido dice "inmediatamente después, solicitar los
          // jugadores". Desde acá no se puede (no hay torneo al que
          // colgar la plantilla), así que se dice POR QUÉ y se ofrece el
          // camino, en vez de dejar al admin con un equipo vacío sin
          // saber cómo llenarlo.
          <p className="muted nota-plantilla">
            ℹ La plantilla se carga al inscribir el equipo a un torneo — los jugadores se registran por
            torneo. Después de crearlo vas a poder inscribirlo desde la columna "Plantilla" de la grilla.
          </p>
        )}
      </div>
    );
  }

  return (
    <div className="page">
      <div className="page__header">
        <h1>Equipos</h1>
        <button type="button" onClick={() => setModo({ tipo: "crear" })}>
          + Nuevo equipo
        </button>
      </div>

      <FiltrosRecurso
        selects={[
          {
            name: "disciplina",
            label: "Disciplina",
            value: disciplinaFiltro,
            options: catalogo.disciplinas.map((d) => ({ value: String(d.id), label: d.nombre })),
            onChange: (v) => {
              setDisciplinaFiltro(v);
              // La modalidad elegida pertenece a la disciplina anterior:
              // dejarla puesta filtraría a vacío por construcción.
              setModalidadFiltro("");
            },
          },
          {
            name: "categoria",
            label: "Categoría",
            value: modalidadFiltro,
            options: catalogo
              .modalidadesDe(disciplinaFiltro ? Number(disciplinaFiltro) : null)
              .map((m) => ({ value: String(m.id), label: m.nombre })),
            onChange: setModalidadFiltro,
          },
          {
            name: "estado",
            label: "Estado",
            value: estadoFiltro,
            labelTodas: "Todos",
            options: [
              { value: "Activo", label: "Activo" },
              { value: "Inactivo", label: "Inactivo" },
            ],
            onChange: setEstadoFiltro,
          },
        ]}
        busqueda={{
          value: busqueda,
          label: "Buscar equipo",
          placeholder: "Buscar por nombre...",
          onChange: setBusqueda,
        }}
        hayFiltrosAplicados={hayFiltros}
        onLimpiar={limpiarFiltros}
      />

      {/* Mejora #1: hasta acá, la fila 201 simplemente no existía para el
          frontend — sin banner, sin aviso, sin paginación. Un fallo
          silencioso pasa a ser uno visible. */}
      {crud.truncado && (
        <p className="muted">
          Mostrando los primeros {LIMITE_LISTA} equipos. Filtrá por disciplina o categoría para ver el resto.
        </p>
      )}

      {crud.softDelete.isError && <p className="error-text">{apiErrorMessage(crud.softDelete.error)}</p>}

      <ResourceTable<EquipoRow>
        rows={filas}
        columns={columnas}
        isLoading={crud.listQuery.isLoading || catalogo.cargando}
        isError={crud.listQuery.isError}
        // El vacío filtrado NO dice lo mismo que el vacío real: un
        // empty-state que no los distingue manda al admin a crear un
        // duplicado de un equipo que ya existe en otra disciplina.
        emptyMessage={
          hayFiltros
            ? "Ningún equipo coincide con estos filtros. Probá limpiarlos."
            : "No hay equipos creados todavía."
        }
        onSelect={(fila) => setModo({ tipo: "editar", fila })}
        onSoftDelete={(fila) => crud.softDelete.mutate(fila.id)}
        softDeletePending={crud.softDelete.isPending}
      />
    </div>
  );
}
