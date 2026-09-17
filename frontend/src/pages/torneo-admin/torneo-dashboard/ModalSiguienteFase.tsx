import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { api, apiErrorMessage } from "../../../api/client";

type AccionDisponible = "cerrar_directo" | "generar_playoffs";
type FormatoEliminatoria = "Unico" | "Ida_Vuelta" | "Mixto";

interface PosicionRow {
  equipo_id: number;
  equipo: string;
  pj: number;
  pts: number;
  dg: number;
  gf: number;
}

// Referencia estable — ver el comentario en `PasoCerrarDirecto` sobre por
// qué un `[]` literal nuevo en cada render rompía el useMemo/useEffect de
// bloques de empate.
const TABLA_VACIA: PosicionRow[] = [];

const FORMATO_OPCIONES: { value: FormatoEliminatoria; titulo: string; subtitulo: string }[] = [
  { value: "Unico", titulo: "Único", subtitulo: "Un partido por cruce, hasta la final." },
  { value: "Ida_Vuelta", titulo: "Ida y vuelta", subtitulo: "Dos partidos por cruce, final incluida." },
  { value: "Mixto", titulo: "Mixto", subtitulo: "Ida y vuelta salvo la final, a un partido." },
];

/** Cierre de Fase Regular + Llaves + Playoffs
 * (docs/plans/cierre-fase-regular-llaves-playoffs-plan.md, E2): reemplaza
 * y absorbe `ModalClasificadosPorGrupo` — antes era el único paso previo
 * a generar playoffs, ahora es el paso 2b de este mismo flujo. Dos
 * caminos EXCLUYENTES (radios, nunca dos botones sueltos): terminar el
 * torneo por tabla, o jugar playoffs. El modal nunca ofrece una opción
 * que el servidor vaya a rechazar — `acciones_disponibles` (GET
 * /estado-fase) ya filtró eso antes de que este componente se monte. */
export function ModalSiguienteFase(props: {
  torneoId: number;
  accionesDisponibles: AccionDisponible[];
  formatoEliminatoriaActual: FormatoEliminatoria;
  clasificadosPorGrupoActual: number | null;
  onClose: () => void;
  onCerrado: () => void;
  onPlayoffsGenerados: () => void;
}) {
  const { torneoId, accionesDisponibles, formatoEliminatoriaActual, clasificadosPorGrupoActual, onClose, onCerrado, onPlayoffsGenerados } = props;
  const queryClient = useQueryClient();

  // D9: cuando solo hay una acción disponible, el paso 1 (radio de un
  // solo elemento) se salta — es una pantalla muerta.
  const [camino, setCamino] = useState<AccionDisponible | null>(
    accionesDisponibles.length === 1 ? accionesDisponibles[0] : null,
  );
  const mostrarPaso1 = accionesDisponibles.length > 1;

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);

  function invalidar() {
    queryClient.invalidateQueries({ queryKey: ["partidos"] });
    queryClient.invalidateQueries({ queryKey: ["bracket", torneoId] });
    queryClient.invalidateQueries({ queryKey: ["torneo", torneoId] });
    queryClient.invalidateQueries({ queryKey: ["torneos", torneoId] });
    queryClient.invalidateQueries({ queryKey: ["estado-fase", torneoId] });
  }

  const anchoPaso2 = camino != null;

  return (
    <div className="modal-overlay" role="dialog" aria-modal="true" aria-labelledby="modal-siguiente-fase-titulo">
      <div className={`modal-panel${anchoPaso2 ? " modal-panel--ancho" : ""}`}>
        {mostrarPaso1 && camino == null && (
          <>
            <p className="modal-panel__paso">Paso 1 de 2 · Camino</p>
            <h2 id="modal-siguiente-fase-titulo">Configurar Siguiente Fase</h2>
            <div className="resource-form">
              {accionesDisponibles.includes("cerrar_directo") && (
                <label className="modal-panel__equipo-fila">
                  <input type="radio" name="camino" checked={false} onChange={() => setCamino("cerrar_directo")} />
                  <span>
                    Terminar el torneo (campeones por tabla)
                    <br />
                    <span className="muted--cuerpo">No vas a poder cargar más resultados después de esto.</span>
                  </span>
                </label>
              )}
              {accionesDisponibles.includes("generar_playoffs") && (
                <label className="modal-panel__equipo-fila">
                  <input type="radio" name="camino" checked={false} onChange={() => setCamino("generar_playoffs")} />
                  <span>Jugar Playoffs</span>
                </label>
              )}
            </div>
            <div className="resource-form__actions">
              <button type="button" className="link-button" onClick={onClose}>
                Cancelar
              </button>
            </div>
          </>
        )}

        {camino === "cerrar_directo" && (
          <PasoCerrarDirecto
            torneoId={torneoId}
            mostrarVolver={mostrarPaso1}
            onVolver={() => setCamino(null)}
            onCancelar={onClose}
            onCerrado={() => {
              invalidar();
              onCerrado();
            }}
          />
        )}

        {camino === "generar_playoffs" && (
          <PasoGenerarPlayoffs
            torneoId={torneoId}
            formatoEliminatoriaActual={formatoEliminatoriaActual}
            clasificadosPorGrupoActual={clasificadosPorGrupoActual}
            mostrarVolver={mostrarPaso1}
            onVolver={() => setCamino(null)}
            onCancelar={onClose}
            onGenerado={() => {
              invalidar();
              onPlayoffsGenerados();
            }}
          />
        )}
      </div>
    </div>
  );
}

/** Paso 2a — preview del podio leído de la tabla de posiciones +
 * confirmación explícita: es una acción de una sola vía, el usuario ve
 * exactamente a quién está coronando antes de apretar. Un empate real en
 * pts/dg/gf se detecta EN EL PREVIEW (Finding 2 / Design review): el
 * servidor solo es el guard de fondo, nunca el primer lugar donde el
 * admin se entera. */
function PasoCerrarDirecto(props: {
  torneoId: number;
  mostrarVolver: boolean;
  onVolver: () => void;
  onCancelar: () => void;
  onCerrado: () => void;
}) {
  const { torneoId, mostrarVolver, onVolver, onCancelar, onCerrado } = props;

  const tablaQuery = useQuery({
    queryKey: ["tabla-posiciones", torneoId],
    queryFn: async () => {
      const { data, error } = await api.GET("/api/v1/estadisticas/torneos/{torneo_id}/posiciones", {
        params: { path: { torneo_id: torneoId } },
      } as never);
      if (error) throw error;
      return data as PosicionRow[];
    },
  });

  // Bloques de empate real (mismo pts/dg/gf), en el orden que ya viene la
  // tabla — solo importa si el bloque cae dentro de los primeros 3.
  // `?? TABLA_VACIA` (referencia ESTABLE, no un `[]` literal nuevo en cada
  // render): con un literal nuevo, el `useMemo` de `bloques` (dependiente
  // de `tabla`) recalculaba en cada render mientras la query está
  // `loading` — inofensivo por sí solo, pero es la clase de bug que
  // rompió esto mismo antes de que `overrides` dejara de sembrarse desde
  // un efecto (ver comentario ahí abajo).
  const tabla = tablaQuery.data ?? TABLA_VACIA;
  const bloques = useMemo(() => {
    const out: PosicionRow[][] = [];
    for (const fila of tabla) {
      const ultimo = out.at(-1);
      if (ultimo && ultimo[0].pts === fila.pts && ultimo[0].dg === fila.dg && ultimo[0].gf === fila.gf) {
        ultimo.push(fila);
      } else {
        out.push([fila]);
      }
    }
    return out;
  }, [tabla]);

  const slots = Math.min(3, tabla.length);
  // Overrides EXPLÍCITOS del admin — clave = "pts-dg-gf", valor = lista de
  // equipo_id en el orden elegido. Sin entrada para una clave = "todavía
  // sin tocar", y el orden efectivo cae al de la tabla (calculado al
  // vuelo en cada lectura, nunca "sembrado" en un efecto — oxlint
  // react(set-state-in-effect): un `setState` síncrono dentro de un
  // efecto derivado de otro estado es la misma clase de bug que ya
  // produjo un loop infinito acá, ver TABLA_VACIA más arriba).
  const [overrides, setOverrides] = useState<Map<string, number[]>>(new Map());

  function ordenDeBloque(bloque: PosicionRow[], clave: string): number[] {
    return overrides.get(clave) ?? bloque.map((f) => f.equipo_id);
  }

  const tablaFinal = useMemo(() => {
    const out: PosicionRow[] = [];
    for (const bloque of bloques) {
      if (bloque.length === 1) {
        out.push(bloque[0]);
        continue;
      }
      const clave = `${bloque[0].pts}-${bloque[0].dg}-${bloque[0].gf}`;
      const orden = ordenDeBloque(bloque, clave);
      const porId = new Map(bloque.map((f) => [f.equipo_id, f]));
      for (const id of orden) {
        const fila = porId.get(id);
        if (fila) out.push(fila);
      }
    }
    return out;
    // eslint-disable-next-line react-hooks/exhaustive-deps -- ordenDeBloque lee `overrides`, ya listado.
  }, [bloques, overrides]);

  // ¿Algún bloque empatado cae DENTRO de los primeros `slots` puestos? —
  // determina si hace falta un orden explícito antes de poder confirmar.
  let posicion = 0;
  let hayEmpateEnPodio = false;
  for (const bloque of bloques) {
    if (bloque.length > 1 && posicion < slots) hayEmpateEnPodio = true;
    posicion += bloque.length;
  }

  function moverEnBloque(clave: string, ids: number[], index: number, direccion: -1 | 1) {
    const nuevo = [...ids];
    const destino = index + direccion;
    if (destino < 0 || destino >= nuevo.length) return;
    [nuevo[index], nuevo[destino]] = [nuevo[destino], nuevo[index]];
    setOverrides((prev) => new Map(prev).set(clave, nuevo));
  }

  const cerrar = useMutation({
    mutationFn: async () => {
      const ordenPodio = hayEmpateEnPodio
        ? tablaFinal.slice(0, slots).map((f) => f.equipo_id)
        : undefined;
      const { data, error } = await api.POST("/api/v1/torneos/{torneo_id}/cerrar", {
        params: { path: { torneo_id: torneoId } },
        body: ordenPodio ? { orden_podio: ordenPodio } : {},
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: onCerrado,
  });

  const campeon = tablaFinal[0] ? tablaFinal[0].equipo : null;

  return (
    <>
      {mostrarVolver && <p className="modal-panel__paso">Paso 2 de 2 · Cerrar torneo</p>}
      <h2 id="modal-siguiente-fase-titulo">Cerrar torneo y coronar campeones</h2>
      {tablaQuery.isLoading && <p className="muted">Cargando la tabla de posiciones...</p>}
      {tablaQuery.isError && <p className="error-text">{apiErrorMessage(tablaQuery.error)}</p>}
      {tabla.length > 0 && (
        <div className="modal-panel__checklist" style={{ maxHeight: "none" }}>
          {tablaFinal.slice(0, slots).map((fila, i) => {
            const clave = `${fila.pts}-${fila.dg}-${fila.gf}`;
            const bloque = bloques.find((b) => b.length > 1 && `${b[0].pts}-${b[0].dg}-${b[0].gf}` === clave);
            const ordenBloque = bloque ? ordenDeBloque(bloque, clave) : undefined;
            const indexEnBloque = bloque && ordenBloque ? ordenBloque.indexOf(fila.equipo_id) : -1;
            return (
              <div key={fila.equipo_id} className="modal-panel__equipo-fila">
                <span>
                  {i + 1}° {fila.equipo}
                  <br />
                  <span className="muted--cuerpo">
                    Pts {fila.pts} · DG {fila.dg} · GF {fila.gf}
                    {bloque && " — Desempatado por orden manual"}
                  </span>
                </span>
                {bloque && ordenBloque && (
                  <span>
                    <button
                      type="button"
                      className="alineacion-fila__mover"
                      aria-label={`Subir a ${fila.equipo}`}
                      disabled={indexEnBloque <= 0}
                      onClick={() => moverEnBloque(clave, ordenBloque, indexEnBloque, -1)}
                    >
                      ↑
                    </button>
                    <button
                      type="button"
                      className="alineacion-fila__mover"
                      aria-label={`Bajar a ${fila.equipo}`}
                      disabled={indexEnBloque >= ordenBloque.length - 1}
                      onClick={() => moverEnBloque(clave, ordenBloque, indexEnBloque, 1)}
                    >
                      ↓
                    </button>
                  </span>
                )}
              </div>
            );
          })}
        </div>
      )}
      {tabla.length === 0 && !tablaQuery.isLoading && !tablaQuery.isError && (
        <p className="error-text">No hay equipos con partidos jugados todavía — no se puede armar el podio.</p>
      )}
      {cerrar.isError && <p className="error-text">{apiErrorMessage(cerrar.error)}</p>}
      <div className="resource-form__actions">
        {mostrarVolver ? (
          <button type="button" className="link-button" onClick={onVolver}>
            ← Volver
          </button>
        ) : (
          <button type="button" className="link-button" onClick={onCancelar}>
            Cancelar
          </button>
        )}
        <button type="button" disabled={cerrar.isPending || tabla.length === 0} onClick={() => cerrar.mutate()}>
          {cerrar.isPending ? "Cerrando..." : `Cerrar torneo y coronar a ${campeon ?? "…"}`}
        </button>
      </div>
    </>
  );
}

/** Paso 2b — absorbe ModalClasificadosPorGrupo (clasificados por grupo /
 * de la tabla) y suma el selector de formato de eliminatoria. */
function PasoGenerarPlayoffs(props: {
  torneoId: number;
  formatoEliminatoriaActual: FormatoEliminatoria;
  clasificadosPorGrupoActual: number | null;
  mostrarVolver: boolean;
  onVolver: () => void;
  onCancelar: () => void;
  onGenerado: () => void;
}) {
  const { torneoId, formatoEliminatoriaActual, clasificadosPorGrupoActual, mostrarVolver, onVolver, onCancelar, onGenerado } = props;
  const [clasificados, setClasificados] = useState(String(clasificadosPorGrupoActual ?? 2));
  const [formato, setFormato] = useState<FormatoEliminatoria>(formatoEliminatoriaActual);

  const n = Number(clasificados);
  const esValido = clasificados !== "" && Number.isInteger(n) && n >= 1;

  const generar = useMutation({
    mutationFn: async () => {
      const { data, error } = await api.POST("/api/v1/torneos/{torneo_id}/playoffs", {
        params: { path: { torneo_id: torneoId } },
        body: { clasificados_por_grupo: n, formato_eliminatoria: formato },
      } as never);
      if (error) throw error;
      return data;
    },
    onSuccess: onGenerado,
  });

  return (
    <>
      {mostrarVolver && <p className="modal-panel__paso">Paso 2 de 2 · Playoffs</p>}
      <h2 id="modal-siguiente-fase-titulo">Generar Playoffs</h2>
      <p className="muted--cuerpo">
        Se usan para armar los cruces de la Fase Eliminatoria. El valor queda guardado para la próxima vez.
      </p>
      <div className="resource-form">
        <label>
          Clasificados por grupo
          <input type="number" min={1} value={clasificados} onChange={(e) => setClasificados(e.target.value)} autoFocus />
        </label>
        {!esValido && clasificados !== "" && <p className="error-text">Tiene que ser al menos 1.</p>}

        <p className="muted--cuerpo">Formato de eliminatoria</p>
        {FORMATO_OPCIONES.map((op) => (
          <label key={op.value} className="modal-panel__equipo-fila">
            <input type="radio" name="formato-eliminatoria" checked={formato === op.value} onChange={() => setFormato(op.value)} />
            <span>
              {op.titulo}
              <br />
              <span className="muted--cuerpo">{op.subtitulo}</span>
            </span>
          </label>
        ))}
        {formato !== "Unico" && (
          <p className="muted--cuerpo">La vuelta se agenda 7 días después de la ida. Podés mover las fechas después desde cada partido.</p>
        )}
      </div>
      {generar.isError && <p className="error-text">{apiErrorMessage(generar.error)}</p>}
      <div className="resource-form__actions">
        {mostrarVolver ? (
          <button type="button" className="link-button" onClick={onVolver}>
            ← Volver
          </button>
        ) : (
          <button type="button" className="link-button" onClick={onCancelar}>
            Cancelar
          </button>
        )}
        <button type="button" disabled={!esValido || generar.isPending} onClick={() => generar.mutate()}>
          {generar.isPending ? "Generando..." : "Generar Playoffs"}
        </button>
      </div>
    </>
  );
}
