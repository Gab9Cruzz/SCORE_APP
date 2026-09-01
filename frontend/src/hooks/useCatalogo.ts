import { useMemo } from "react";
// 3A-6 (docs/plans/cierre-backlog-todos-plan.md): ModalidadRow acá era la
// 4ta declaración ad-hoc del mismo shape que components["schemas"]["ModalidadOut"]
// ya genera — re-exportado desde el alias central en vez de mantener dos
// fuentes de verdad para la misma forma.
import type { Modalidad as ModalidadRow } from "../api/types";
import { useResourceCrud } from "./useResourceCrud";

export interface DisciplinaRow {
  id: number;
  nombre: string;
  estado: string;
  // NULL = sin ranking asignado, ordena al final — barra de navegación
  // tipo SofaScore (motor-formatos-plantillas-navegacion-plan.md, #3).
  orden_popularidad: number | null;
}

export type { ModalidadRow };

/**
 * Catálogo Disciplina/Modalidad en un solo lugar
 * (equipos-disciplina-navegacion-plan.md, Mejora #2).
 *
 * Antes de este hook, seis componentes construían por su cuenta el mismo
 * par de `Map` (TorneosAdmin, TorneoDashboard, EquiposDelTorneo,
 * ModalAgregarInscripcion + los dos que este plan agrega): cuatro
 * `useResourceCrud` sobre los mismos dos endpoints y cuatro `useMemo` con
 * la misma lógica.
 *
 * El beneficio NO es de red — TanStack Query ya deduplica por `queryKey`,
 * y estos dos siguen siendo los mismos "disciplinas"/"modalidades" de
 * siempre, así que el cache se comparte igual que antes. El beneficio es
 * que "cómo se cruza el catálogo" existe en un archivo: cuando haya que
 * agregar iconos, o filtrar `estado=Activo` por defecto, se toca acá y no
 * en seis lugares.
 */
export function useCatalogo() {
  const disciplinas = useResourceCrud<DisciplinaRow>({
    resourceKey: "disciplinas",
    basePath: "/api/v1/disciplinas",
  });
  const modalidades = useResourceCrud<ModalidadRow>({
    resourceKey: "modalidades",
    basePath: "/api/v1/modalidades",
  });

  const listaDisciplinas = useMemo(() => disciplinas.listQuery.data ?? [], [disciplinas.listQuery.data]);
  const listaModalidades = useMemo(() => modalidades.listQuery.data ?? [], [modalidades.listQuery.data]);

  const disciplinaPorId = useMemo(
    () => new Map(listaDisciplinas.map((d) => [d.id, d])),
    [listaDisciplinas],
  );
  const modalidadPorId = useMemo(() => new Map(listaModalidades.map((m) => [m.id, m])), [listaModalidades]);

  const modalidadesPorDisciplina = useMemo(() => {
    const agrupadas = new Map<number, ModalidadRow[]>();
    for (const m of listaModalidades) {
      const actuales = agrupadas.get(m.disciplina_id);
      if (actuales) actuales.push(m);
      else agrupadas.set(m.disciplina_id, [m]);
    }
    return agrupadas;
  }, [listaModalidades]);

  /** Las modalidades de una disciplina, o [] si todavía no hay ninguna
   * elegida — el caso normal al abrir un formulario, no un error. */
  function modalidadesDe(disciplinaId: number | null | undefined): ModalidadRow[] {
    if (disciplinaId == null) return [];
    return modalidadesPorDisciplina.get(disciplinaId) ?? [];
  }

  /** Nombre listo para mostrar, con el guion largo que el resto del
   * módulo ya usa para "todavía no lo sé" (no un id crudo en pantalla). */
  const nombreDisciplina = (id: number | null | undefined) =>
    id == null ? "—" : (disciplinaPorId.get(id)?.nombre ?? "—");
  const nombreModalidad = (id: number | null | undefined) =>
    id == null ? "—" : (modalidadPorId.get(id)?.nombre ?? "—");

  return {
    disciplinas: listaDisciplinas,
    modalidades: listaModalidades,
    disciplinaPorId,
    modalidadPorId,
    modalidadesDe,
    nombreDisciplina,
    nombreModalidad,
    cargando: disciplinas.listQuery.isLoading || modalidades.listQuery.isLoading,
    error: disciplinas.listQuery.isError || modalidades.listQuery.isError,
  };
}
