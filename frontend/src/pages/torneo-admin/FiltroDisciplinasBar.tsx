import { useRef } from "react";
import { iconoDisciplina, inicialDisciplina } from "./iconosDisciplina";

export interface ChipDisciplina {
  id: number;
  nombre: string;
}
export interface ChipModalidad {
  id: number;
  nombre: string;
}
export interface ChipEstado {
  valor: string;
  nombre: string;
}

interface FiltroDisciplinasBarProps {
  disciplinas: ChipDisciplina[];
  /** Modalidades de la disciplina seleccionada que TIENEN torneos. La
   * segunda fila aparece solo si hay 2 o más (una sola modalidad no es
   * una elección, es un dato). */
  modalidades: ChipModalidad[];
  disciplinaSeleccionada: number | null;
  modalidadSeleccionada: number | null;
  onSeleccionarDisciplina: (id: number | null) => void;
  onSeleccionarModalidad: (id: number | null) => void;
  /** 3A-9 (docs/plans/cierre-backlog-todos-plan.md): estados presentes
   * entre los torneos YA cargados (mismo criterio D-Eng-16 que
   * disciplinas/modalidades — nunca un chip que filtre a vacío). Opcional:
   * el componente sin esta prop se comporta exactamente igual que antes
   * (sin fila de Estado) — no todo consumidor de esta barra tiene un
   * concepto de "estado" que filtrar. */
  estados?: ChipEstado[];
  estadoSeleccionado?: string | null;
  onSeleccionarEstado?: (valor: string | null) => void;
}

/** Barra de navegación horizontal tipo SofaScore para la Pestaña Torneos
 * (equipos-disciplina-navegacion-plan.md, Fase 2 parte D).
 *
 * Tres decisiones que la hacen usable y no un muro:
 *
 * 1. Solo muestra disciplinas QUE TIENEN TORNEOS (Decisión #6), no las 28
 *    del catálogo. 94 chips entre disciplinas y modalidades no son
 *    navegación. Como efecto secundario, ningún chip puede filtrar a
 *    vacío: la lista de chips se deriva de los mismos torneos que filtra.
 *
 * 2. Dos niveles, no uno (Decisión #7). Modalidad es hija de Disciplina;
 *    aplanarlas obligaría a leer "Fútbol 11" como hermana de "Tenis". La
 *    segunda fila es condicional.
 *
 * 3. `<button>` reales dentro de un `role="tablist"`, con `aria-pressed` y
 *    flechas ←→ para mover el foco. Un `<div onClick>` deja el filtro
 *    inalcanzable sin mouse, y el estado activo se marca con fondo sólido
 *    además del color (el color solo falla en monocromo y en WCAG).
 *
 * El componente no decide NADA sobre los datos: recibe los chips ya
 * calculados y devuelve el id elegido. Quien lo usa (TorneosAdminPage) es
 * el dueño del estado del filtro. */
export function FiltroDisciplinasBar(props: FiltroDisciplinasBarProps) {
  const {
    disciplinas,
    modalidades,
    disciplinaSeleccionada,
    modalidadSeleccionada,
    onSeleccionarDisciplina,
    onSeleccionarModalidad,
    estados = [],
    estadoSeleccionado = null,
    onSeleccionarEstado,
  } = props;

  const filaDisciplinas = useRef<HTMLDivElement>(null);
  const filaModalidades = useRef<HTMLDivElement>(null);
  const filaEstados = useRef<HTMLDivElement>(null);

  /** Flechas ←→ mueven el foco entre los chips de la misma fila, que es lo
   * que un `role="tablist"` promete. Sin esto el `role` es una mentira
   * para un lector de pantalla. */
  function moverFoco(e: React.KeyboardEvent, contenedor: HTMLDivElement | null) {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    const chips = Array.from(contenedor?.querySelectorAll<HTMLButtonElement>("button") ?? []);
    const actual = chips.indexOf(document.activeElement as HTMLButtonElement);
    if (actual === -1) return;
    e.preventDefault();
    const siguiente = e.key === "ArrowRight" ? actual + 1 : actual - 1;
    chips[(siguiente + chips.length) % chips.length]?.focus();
  }

  return (
    <div className="filtro-disciplinas">
      <div
        className="filtro-disciplinas__fila"
        role="tablist"
        aria-label="Filtrar por disciplina"
        ref={filaDisciplinas}
        onKeyDown={(e) => moverFoco(e, filaDisciplinas.current)}
      >
        <button
          type="button"
          role="tab"
          className={`chip-disciplina${disciplinaSeleccionada === null ? " chip-disciplina--activo" : ""}`}
          aria-pressed={disciplinaSeleccionada === null}
          aria-selected={disciplinaSeleccionada === null}
          onClick={() => onSeleccionarDisciplina(null)}
        >
          <span className="chip-disciplina__icono" aria-hidden="true">
            ⬤
          </span>
          Todos
        </button>
        {disciplinas.map((d) => {
          const activo = disciplinaSeleccionada === d.id;
          const emoji = iconoDisciplina(d.nombre);
          return (
            <button
              key={d.id}
              type="button"
              role="tab"
              className={`chip-disciplina${activo ? " chip-disciplina--activo" : ""}`}
              aria-pressed={activo}
              aria-selected={activo}
              onClick={() => onSeleccionarDisciplina(activo ? null : d.id)}
            >
              <span className="chip-disciplina__icono" aria-hidden="true">
                {emoji ?? inicialDisciplina(d.nombre)}
              </span>
              {d.nombre}
            </button>
          );
        })}
      </div>

      {/* Segunda fila: solo con 2+ modalidades presentes (Decisión #7) —
          con una sola, elegirla no filtra nada y ocupa una fila entera. */}
      {disciplinaSeleccionada !== null && modalidades.length > 1 && (
        <div
          className="filtro-disciplinas__fila filtro-disciplinas__fila--modalidades"
          role="tablist"
          aria-label="Filtrar por modalidad"
          ref={filaModalidades}
          onKeyDown={(e) => moverFoco(e, filaModalidades.current)}
        >
          <button
            type="button"
            role="tab"
            className={`chip-modalidad${modalidadSeleccionada === null ? " chip-modalidad--activo" : ""}`}
            aria-pressed={modalidadSeleccionada === null}
            aria-selected={modalidadSeleccionada === null}
            onClick={() => onSeleccionarModalidad(null)}
          >
            Todas
          </button>
          {modalidades.map((m) => {
            const activo = modalidadSeleccionada === m.id;
            return (
              <button
                key={m.id}
                type="button"
                role="tab"
                className={`chip-modalidad${activo ? " chip-modalidad--activo" : ""}`}
                aria-pressed={activo}
                aria-selected={activo}
                onClick={() => onSeleccionarModalidad(activo ? null : m.id)}
              >
                {m.nombre}
              </button>
            );
          })}
        </div>
      )}

      {/* 3A-9: fila de Estado, mismo criterio "2+ o no se muestra" que la
          de Modalidad — siempre disponible (no depende de haber elegido
          Disciplina), es un eje de filtro independiente. */}
      {onSeleccionarEstado && estados.length > 1 && (
        <div
          className="filtro-disciplinas__fila filtro-disciplinas__fila--estados"
          role="tablist"
          aria-label="Filtrar por estado"
          ref={filaEstados}
          onKeyDown={(e) => moverFoco(e, filaEstados.current)}
        >
          <button
            type="button"
            role="tab"
            className={`chip-modalidad${estadoSeleccionado === null ? " chip-modalidad--activo" : ""}`}
            aria-pressed={estadoSeleccionado === null}
            aria-selected={estadoSeleccionado === null}
            onClick={() => onSeleccionarEstado(null)}
          >
            Todos los estados
          </button>
          {estados.map((e) => {
            const activo = estadoSeleccionado === e.valor;
            return (
              <button
                key={e.valor}
                type="button"
                role="tab"
                className={`chip-modalidad${activo ? " chip-modalidad--activo" : ""}`}
                aria-pressed={activo}
                aria-selected={activo}
                onClick={() => onSeleccionarEstado(activo ? null : e.valor)}
              >
                {e.nombre}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
