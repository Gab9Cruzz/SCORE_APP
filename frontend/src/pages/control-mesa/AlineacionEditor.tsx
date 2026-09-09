import { useCallback, useEffect, useRef, useState } from "react";
import {
  type JugadorPlantilla,
  type Seleccion,
  type Zona,
  alternarConvocado,
  contarConvocados,
  contarTitulares,
  hayLugarParaTitular,
  marcarPrimerosComoTitulares,
  mover,
  ordenarPlantilla,
} from "./alineacion";
import { useArrastreHabilitado, usePointerDrag } from "./usePointerDrag";

/** Paso 1 (convocados) + Paso 2 (titulares/suplentes) de un equipo.
 *
 * Una sola pantalla con dos zonas, no un wizard de pasos bloqueados: los dos
 * pasos operan sobre el MISMO dato y el operador va y viene (marca presentes,
 * sube titulares, se acuerda de uno más, vuelve a marcar). Un wizard lo
 * obligaría a retroceder por cada corrección.
 *
 * El Paso 1 arranca ARRIBA de las zonas mientras está expandido: en un partido
 * nuevo lo primero que ve el operador son dos cajas vacías, y su única acción
 * posible no puede quedar debajo de ellas, fuera del fold en 375px.
 */
export function AlineacionEditor(props: {
  plantilla: JugadorPlantilla[];
  seleccion: Seleccion;
  onCambiar: (s: Seleccion) => void;
  minimo: number;
  /** Área 1 (modo-vivo-sustituciones-cierre-plan.md, T2): tope SUPERIOR de
   * titulares para este equipo — `preflight-inicio` lo publica junto con
   * `minimo` (mismo origen: Torneo.maximo_titulares_permitido o
   * Modalidad.tamano_equipo), así este editor nunca reimplementa de dónde
   * sale el número. */
  maximo: number;
  /** Con el partido ya iniciado solo se puede sumar al banco: no se renderiza
   * el botón de bajar a suplentes ni se permite destildar convocados. */
  enCurso: boolean;
  /** Alta aditiva de un jugador con el partido en curso (llegada tardía). */
  onSumarTardio?: (perfilId: number) => void;
  sumandoTardio?: boolean;
}) {
  const { plantilla, seleccion, onCambiar, minimo, maximo, enCurso, onSumarTardio, sumandoTardio } = props;
  const [pasoAbierto, setPasoAbierto] = useState(false);
  const [anuncio, setAnuncio] = useState("");
  // Design Fase 2, Pass 2 (T10): "intento de exceso" es un GAP crítico si
  // queda silencioso — nunca un no-op sin explicación. Sin un sistema de
  // toast en el repo (ver ModalPerfilJugador.tsx: la convención acá es
  // mensaje inline, no un toast genérico), esto es un mensaje inline junto
  // a la zona de Titulares, con `role="alert"` para que un lector de
  // pantalla lo anuncie igual que un toast lo haría.
  const [errorTope, setErrorTope] = useState<string | null>(null);
  const arrastreHabilitado = useArrastreHabilitado();

  const zonaRefs = useRef<Record<Zona, HTMLDivElement | null>>({ titulares: null, suplentes: null });
  // Para devolver el foco al botón del jugador movido en su zona nueva: sin
  // esto el botón presionado desaparece de esa zona y el foco cae en <body>,
  // que deja a un usuario de teclado al principio del documento.
  const botonRefs = useRef<Map<number, HTMLButtonElement>>(new Map());
  const focoPendiente = useRef<number | null>(null);

  useEffect(() => {
    if (focoPendiente.current == null) return;
    botonRefs.current.get(focoPendiente.current)?.focus();
    focoPendiente.current = null;
  });

  const titulares = ordenarPlantilla(plantilla.filter((j) => seleccion.get(j.jugador_perfil_id) === true));
  const suplentes = ordenarPlantilla(plantilla.filter((j) => seleccion.get(j.jugador_perfil_id) === false));
  const nTitulares = contarTitulares(seleccion, plantilla);
  const nConvocados = contarConvocados(seleccion, plantilla);
  const faltan = Math.max(0, minimo - nTitulares);

  const moverA = useCallback(
    (perfilId: number, zona: Zona) => {
      if (enCurso && zona === "suplentes") return; // no se degrada en vivo
      const jugador = plantilla.find((j) => j.jugador_perfil_id === perfilId);
      if (zona === "titulares" && !hayLugarParaTitular(seleccion, plantilla, maximo)) {
        // Rechazo explícito (T2/T10) — nunca un no-op silencioso: el
        // movimiento NO se aplica, y el motivo queda visible hasta el
        // próximo intento (se limpia recién cuando el operador logra un
        // movimiento válido, no con un timeout que podría desaparecer
        // antes de que lo lea bajo presión).
        setErrorTope(
          `Ya hay ${maximo} titulares para este equipo — bajá alguno a suplente antes de subir a ` +
            `${jugador?.jugador ?? "otro jugador"}.`,
        );
        return;
      }
      const siguiente = mover(seleccion, perfilId, zona);
      if (siguiente === seleccion) return; // no-op: ya estaba en esa zona
      setErrorTope(null);
      onCambiar(siguiente);
      focoPendiente.current = perfilId;
      // Se anuncia el resultado, no el gesto: al soltar o al tocar, una sola vez.
      setAnuncio(
        `${jugador?.jugador ?? "Jugador"} movido a ${zona === "titulares" ? "Titulares" : "Suplentes"}. ` +
          `${zona === "titulares" ? nTitulares + 1 : nTitulares - 1} de ${minimo}.`,
      );
    },
    [enCurso, seleccion, plantilla, onCambiar, nTitulares, minimo, maximo],
  );

  const zonaEnPunto = useCallback((x: number, y: number): Zona | null => {
    for (const zona of ["titulares", "suplentes"] as Zona[]) {
      const el = zonaRefs.current[zona];
      if (!el) continue;
      const r = el.getBoundingClientRect();
      if (x >= r.left && x <= r.right && y >= r.top && y <= r.bottom) return zona;
    }
    return null;
  }, []);

  const { estado: arrastre, propsManija } = usePointerDrag<Zona>({ zonaEnPunto, onSoltar: moverA });

  function renderFila(j: JugadorPlantilla, zona: Zona) {
    const puedeBajar = zona === "titulares" && !enCurso;
    const puedeSubir = zona === "suplentes";
    const arrastrando = arrastre.itemId === j.jugador_perfil_id;
    return (
      <li
        key={j.jugador_perfil_id}
        className={`alineacion-fila${arrastrando ? " alineacion-fila--arrastrando" : ""}`}
        style={arrastrando ? { transform: `translate(${arrastre.dx}px, ${arrastre.dy}px)` } : undefined}
      >
        {arrastreHabilitado && (
          // touch-action: none SOLO acá, nunca en la fila entera: aplicado a la
          // fila impediría scrollear una lista de 18 jugadores con el dedo.
          <span
            className="alineacion-fila__manija"
            aria-hidden="true"
            style={{ touchAction: "none" }}
            {...propsManija(j.jugador_perfil_id)}
          >
            ⠿
          </span>
        )}
        <span className="alineacion-fila__nombre">
          {j.dorsal != null ? `#${j.dorsal} ` : ""}
          {j.jugador}
        </span>
        {(puedeSubir || puedeBajar) && (
          <button
            type="button"
            ref={(el) => {
              if (el) botonRefs.current.set(j.jugador_perfil_id, el);
              else botonRefs.current.delete(j.jugador_perfil_id);
            }}
            className="alineacion-fila__mover"
            aria-label={
              puedeSubir
                ? `Subir a titulares a ${j.jugador}${j.dorsal != null ? `, dorsal ${j.dorsal}` : ""}`
                : `Bajar a suplentes a ${j.jugador}${j.dorsal != null ? `, dorsal ${j.dorsal}` : ""}`
            }
            onClick={() => moverA(j.jugador_perfil_id, puedeSubir ? "titulares" : "suplentes")}
          >
            {puedeSubir ? "↑" : "↓"}
          </button>
        )}
      </li>
    );
  }

  function renderZona(zona: Zona, jugadores: JugadorPlantilla[], titulo: string, vacio: string) {
    const activa = arrastre.zonaActiva === zona && arrastre.itemId != null;
    return (
      <div
        ref={(el) => {
          zonaRefs.current[zona] = el;
        }}
        className={`alineacion-zona${activa ? " alineacion-zona--activa" : ""}`}
      >
        <div className="alineacion-zona__header">
          <h3 id={`zona-${zona}`}>{titulo}</h3>
          {zona === "titulares" ? (
            <span className={`alineacion-contador${faltan > 0 ? " alineacion-contador--falta" : ""}`}>
              {nTitulares} de {minimo}
              {faltan > 0 ? ` · faltan ${faltan}` : " ✓"}
            </span>
          ) : (
            <span className="alineacion-contador">{jugadores.length}</span>
          )}
          {zona === "titulares" && !enCurso && (
            <button
              type="button"
              className="link-button"
              onClick={() => onCambiar(marcarPrimerosComoTitulares(seleccion, plantilla, minimo))}
            >
              Marcar {minimo} por dorsal
            </button>
          )}
        </div>
        {zona === "titulares" && enCurso && (
          // La restricción como texto persistente, no como tooltip: `title=` no
          // existe en touch, que es el dispositivo real del operador.
          <p className="muted">Partido en curso — no se puede sacar titulares.</p>
        )}
        {zona === "titulares" && errorTope && (
          <p className="error-text" role="alert">{errorTope}</p>
        )}
        {jugadores.length === 0 ? (
          <p className="muted">{vacio}</p>
        ) : (
          <ul className="alineacion-lista" aria-labelledby={`zona-${zona}`}>
            {jugadores.map((j) => renderFila(j, zona))}
          </ul>
        )}
      </div>
    );
  }

  const noConvocados = ordenarPlantilla(plantilla.filter((j) => !seleccion.has(j.jugador_perfil_id)));

  return (
    <section className="alineacion-editor">
      <p aria-live="polite" className="sr-only">
        {anuncio}
      </p>

      {/* Paso 1 arriba mientras está expandido; colapsa por acción explícita,
          nunca al primer checkbox (eso cerraría la lista que el operador está
          usando). */}
      <div className="alineacion-paso1">
        <button
          type="button"
          className="link-button"
          aria-expanded={pasoAbierto}
          onClick={() => setPasoAbierto((v) => !v)}
        >
          {pasoAbierto ? "▾" : "▸"} Paso 1 · Convocados {nConvocados} de {plantilla.length} · {suplentes.length} en
          Suplentes
        </button>
        {pasoAbierto && (
          <>
            {plantilla.length === 0 ? (
              <p className="muted">Este equipo no tiene jugadores en el roster del torneo.</p>
            ) : (
              <ul className="convocatoria-lista">
                {ordenarPlantilla(plantilla).map((j) => {
                  const convocado = seleccion.has(j.jugador_perfil_id);
                  return (
                    <li key={j.jugador_perfil_id}>
                      <label>
                        <input
                          type="checkbox"
                          checked={convocado}
                          // En curso los ya convocados quedan en solo lectura:
                          // quitarlos es la operación destructiva que el backend
                          // rechaza, y no se ofrece un control cuya única
                          // respuesta posible es un error.
                          disabled={enCurso && convocado}
                          onChange={() => {
                            if (enCurso) {
                              if (!convocado && onSumarTardio) onSumarTardio(j.jugador_perfil_id);
                              return;
                            }
                            onCambiar(alternarConvocado(seleccion, j.jugador_perfil_id));
                          }}
                        />
                        {j.dorsal != null ? `#${j.dorsal} ` : ""}
                        {j.jugador}
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            {enCurso && noConvocados.length > 0 && (
              <p className="muted">
                {sumandoTardio ? "Sumando…" : "Tildá un jugador para sumarlo al banco sin frenar el partido."}
              </p>
            )}
            <button type="button" onClick={() => setPasoAbierto(false)}>
              Listo, {nConvocados} convocados
            </button>
          </>
        )}
      </div>

      {renderZona("titulares", titulares, "Titulares", "Tocá ↑ en un jugador para subirlo acá.")}
      {renderZona("suplentes", suplentes, "Suplentes", "Todos los convocados están de titulares.")}
    </section>
  );
}
