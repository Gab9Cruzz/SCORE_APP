import type { Modalidad as ModalidadRow } from "../../api/types";
import { apiErrorMessage } from "../../api/client";
import { useResourceCrud } from "../../hooks/useResourceCrud";

interface DisciplinaRow {
  id: number;
  nombre: string;
  estado: "Activo" | "Inactivo";
  modalidades: ModalidadRow[];
}

/** Catálogo maestro de disciplinas y modalidades
 * (ediciones-catalogo-disciplinas-plan.md, Decisión C1) — reemplaza a
 * DisciplinasAdmin.tsx/ModalidadesAdmin.tsx. Ya no es un CRUD: las 28
 * disciplinas / 66 modalidades las carga 11_catalogo_disciplinas.sql, acá
 * solo se puede activar/desactivar una fila (toggle de Estado). Vista
 * jerárquica de una sola llamada (GET /disciplinas/con-modalidades) en vez
 * de cruzar dos listas planas del lado del cliente.
 *
 * No usa SimpleResourceAdminPage: ese patrón asume create+softDelete
 * planos sobre una tabla lisa, y acá no hay ni lo uno ni lo otro (sin
 * POST, PATCH solo togglea Estado, y la forma es jerárquica) — mismo
 * criterio que PerfilJugadorAdmin.tsx para una vista de solo lectura que
 * no encaja en el molde CRUD genérico. */
export function CatalogoDisciplinasPage() {
  // basePath apunta a la vista jerárquica: es de dónde sale `listQuery`.
  // Los toggles de estado (disciplina Y modalidad) van por `customAction`
  // porque cada uno pega a un endpoint propio (/disciplinas/{id} y
  // /modalidades/{id}) distinto del basePath de la lista — mismo patrón
  // que EquiposDelTorneo.tsx usa para acciones que no son un
  // update/softDelete plano sobre ESE basePath.
  const catalogo = useResourceCrud<DisciplinaRow>({
    resourceKey: "disciplinas-catalogo",
    basePath: "/api/v1/disciplinas/con-modalidades",
  });

  function toggleDisciplina(d: DisciplinaRow) {
    catalogo.customAction.mutate({
      path: `/api/v1/disciplinas/${d.id}`,
      method: "PATCH",
      body: { estado: d.estado === "Activo" ? "Inactivo" : "Activo" },
    });
  }

  function toggleModalidad(m: ModalidadRow) {
    catalogo.customAction.mutate({
      path: `/api/v1/modalidades/${m.id}`,
      method: "PATCH",
      body: { estado: m.estado === "Activo" ? "Inactivo" : "Activo" },
    });
  }

  return (
    <div className="page">
      <h1>Catálogo de disciplinas</h1>
      <p className="muted">
        Catálogo maestro precargado — no se pueden crear ni renombrar disciplinas o modalidades acá,
        solo activar/desactivar. Una disciplina o modalidad desactivada deja de ofrecerse para
        torneos nuevos, sin afectar a los que ya la usan.
      </p>

      {catalogo.customAction.isError && (
        <p className="error-text">{apiErrorMessage(catalogo.customAction.error)}</p>
      )}
      {catalogo.listQuery.isLoading && <p>Cargando...</p>}
      {catalogo.listQuery.isError && <p className="error-text">No se pudo cargar el catálogo.</p>}

      <div className="catalogo-disciplinas">
        {catalogo.listQuery.data?.map((d) => (
          <section key={d.id} className="card catalogo-disciplinas__disciplina">
            <div className="catalogo-disciplinas__header">
              <h2>
                {d.nombre} <span className={`badge ${d.estado === "Activo" ? "badge--en-curso" : ""}`}>{d.estado}</span>
              </h2>
              <button type="button" onClick={() => toggleDisciplina(d)} disabled={catalogo.customAction.isPending}>
                {d.estado === "Activo" ? "Desactivar disciplina" : "Activar disciplina"}
              </button>
            </div>

            {d.modalidades.length === 0 ? (
              <p className="muted">Sin modalidades cargadas.</p>
            ) : (
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>Modalidad</th>
                      <th>Tamaño de equipo</th>
                      <th>Estado</th>
                      <th></th>
                    </tr>
                  </thead>
                  <tbody>
                    {d.modalidades.map((m) => (
                      <tr key={m.id}>
                        <td>{m.nombre}</td>
                        <td>{m.tamano_equipo}</td>
                        <td>
                          <span className={`badge ${m.estado === "Activo" ? "badge--en-curso" : ""}`}>{m.estado}</span>
                        </td>
                        <td className="table-actions">
                          <button type="button" onClick={() => toggleModalidad(m)} disabled={catalogo.customAction.isPending}>
                            {m.estado === "Activo" ? "Desactivar" : "Activar"}
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>
        ))}
      </div>
    </div>
  );
}
