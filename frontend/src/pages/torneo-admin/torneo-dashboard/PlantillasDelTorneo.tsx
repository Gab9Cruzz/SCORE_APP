import { useMemo, useState } from "react";
import { Link, useNavigate, useOutletContext } from "react-router-dom";
import type { Equipo as EquipoRow } from "../../../api/types";
import { apiErrorMessage } from "../../../api/client";
import { ResourceForm, type ResourceFieldValue } from "../../../components/admin/ResourceForm";
import { LIMITE_LISTA, useResourceCrud } from "../../../hooks/useResourceCrud";
import { useCatalogo } from "../../../hooks/useCatalogo";
import { AvatarJugador } from "../AvatarJugador";
import { iconoDisciplina } from "../iconosDisciplina";
import type { RegistroLoteAlcanceTorneo } from "../RegistroLoteAdmin";
import { ModalPerfilJugador } from "./ModalPerfilJugador";
import type { TorneoDashboardContext } from "./TorneoDashboard";

interface PlantillaRow {
  id: number;
  jugador_perfil_id: number;
  inscripcion_torneo_id: number;
  dorsal: number | null;
  fecha_inicio: string;
  fecha_fin: string | null;
  estado: string;
}
interface JugadorRow {
  id: number;
  nombre: string;
  foto_url: string | null;
}
interface PerfilRow {
  id: number;
  jugador_id: number;
  disciplina_id: number;
}
interface InscripcionRow {
  id: number;
  equipo_id: number;
}

type Modo = { tipo: "lista" } | { tipo: "crear" } | { tipo: "editar"; fila: PlantillaRow } | { tipo: "baja"; fila: PlantillaRow };

/** Sub-pestaña "Plantillas" del dashboard scoped — grid de tarjetas
 * agrupado por equipo (Design sección D, motor-formatos-plantillas-
 * navegacion-plan.md), reemplaza la tabla plana anterior. Mismo alcance
 * funcional de antes (alta/edición/baja de vínculos jugador↔equipo,
 * acotado a este torneo, sin volver a preguntar la Disciplina) — el grid
 * cambia CÓMO se ve la lista, no qué se puede hacer con ella: "Editar
 * vínculo"/"Dar de baja" siguen siendo las mismas dos pantallas de antes,
 * ahora alcanzables desde cada tarjeta en vez de una fila de tabla. Lo
 * nuevo es el click en la tarjeta, que abre el Perfil de Jugador (editable)
 * en un modal — Decisión Audit #7: mantiene el contexto del grid detrás. */
export function PlantillasDelTorneoPage() {
  const { torneoId, disciplinaId, torneoContexto } = useOutletContext<TorneoDashboardContext>();
  const navigate = useNavigate();
  const [modo, setModo] = useState<Modo>({ tipo: "lista" });
  const [errorPerfil, setErrorPerfil] = useState<string | null>(null);
  const [resolviendoPerfil, setResolviendoPerfil] = useState(false);
  const [perfilAbierto, setPerfilAbierto] = useState<number | null>(null); // jugador_id

  const crud = useResourceCrud<PlantillaRow>({
    resourceKey: "plantillas",
    basePath: "/api/v1/plantillas",
    listParams: { torneo_id: torneoId },
  });
  const jugadores = useResourceCrud<JugadorRow>({ resourceKey: "jugadores", basePath: "/api/v1/jugadores" });
  const perfiles = useResourceCrud<PerfilRow, { jugador_id: number; disciplina_id: number }>({
    resourceKey: "perfiles",
    basePath: "/api/v1/perfiles",
    listParams: { disciplina_id: disciplinaId },
  });
  const inscripciones = useResourceCrud<InscripcionRow>({
    resourceKey: "inscripciones",
    basePath: "/api/v1/inscripciones",
    listParams: { torneo_id: torneoId },
  });
  const equipos = useResourceCrud<EquipoRow>({ resourceKey: "equipos", basePath: "/api/v1/equipos" });
  const catalogo = useCatalogo();

  const jugadorPorId = useMemo(
    () => new Map((jugadores.listQuery.data ?? []).map((j) => [j.id, j])),
    [jugadores.listQuery.data],
  );
  const nombreEquipo = useMemo(
    () => new Map((equipos.listQuery.data ?? []).map((e) => [e.id, e.nombre])),
    [equipos.listQuery.data],
  );
  const nombreEquipoDeInscripcion = useMemo(() => {
    const inscripcionAEquipo = new Map((inscripciones.listQuery.data ?? []).map((i) => [i.id, i.equipo_id]));
    return (inscripcionId: number) => nombreEquipo.get(inscripcionAEquipo.get(inscripcionId) ?? -1) ?? `Inscripción #${inscripcionId}`;
  }, [inscripciones.listQuery.data, nombreEquipo]);
  const perfilPorId = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [p.id, p])),
    [perfiles.listQuery.data],
  );
  const perfilIdPorJugador = useMemo(
    () => new Map((perfiles.listQuery.data ?? []).map((p) => [p.jugador_id, p.id])),
    [perfiles.listQuery.data],
  );

  function jugadorDeVinculo(perfilId: number): JugadorRow | undefined {
    const p = perfilPorId.get(perfilId);
    return p ? jugadorPorId.get(p.jugador_id) : undefined;
  }
  function etiquetaJugador(perfilId: number): string {
    return jugadorDeVinculo(perfilId)?.nombre ?? `Perfil #${perfilId}`;
  }

  // Un card por equipo INSCRITO, no solo por equipo con jugadores — un
  // equipo recién matriculado y sin plantilla todavía es un estado real,
  // no un error (estados de interacción del grid, Fase 2).
  const gruposPorEquipo = useMemo(() => {
    const vinculosPorInscripcion = new Map<number, PlantillaRow[]>();
    for (const p of crud.listQuery.data ?? []) {
      const arr = vinculosPorInscripcion.get(p.inscripcion_torneo_id);
      if (arr) arr.push(p);
      else vinculosPorInscripcion.set(p.inscripcion_torneo_id, [p]);
    }
    return (inscripciones.listQuery.data ?? []).map((i) => {
      const vinculos = vinculosPorInscripcion.get(i.id) ?? [];
      return {
        inscripcionId: i.id,
        equipoNombre: nombreEquipo.get(i.equipo_id) ?? `Equipo #${i.equipo_id}`,
        vinculos,
        activos: vinculos.filter((v) => v.estado === "Activo").length,
      };
    });
  }, [crud.listQuery.data, inscripciones.listQuery.data, nombreEquipo]);

  const iconoTorneo = iconoDisciplina(catalogo.nombreDisciplina(disciplinaId));

  function volver() {
    setModo({ tipo: "lista" });
    setErrorPerfil(null);
  }

  // Mismo patrón resolve-o-crea-el-perfil que ya usaba PlantillasAdmin.tsx
  // (equipos-jugadores-plan.md) — acá la Disciplina no se pregunta, la fija
  // el torneo, así que un alta nueva es un solo campo real: el Jugador.
  async function crearVinculo(values: Record<string, ResourceFieldValue>) {
    setErrorPerfil(null);
    const jugadorId = values.jugador_id as number;
    let perfilId = perfilIdPorJugador.get(jugadorId) ?? null;

    if (perfilId == null) {
      setResolviendoPerfil(true);
      try {
        const nuevoPerfil = await perfiles.create.mutateAsync({ jugador_id: jugadorId, disciplina_id: disciplinaId });
        perfilId = nuevoPerfil.id;
      } catch (e) {
        setErrorPerfil(apiErrorMessage(e, "No se pudo crear el perfil del jugador en esta disciplina."));
        setResolviendoPerfil(false);
        return;
      }
      setResolviendoPerfil(false);
    }

    crud.create.mutate(
      {
        jugador_perfil_id: perfilId,
        inscripcion_torneo_id: values.inscripcion_torneo_id,
        dorsal: values.dorsal,
        fecha_inicio: values.fecha_inicio,
      } as never,
      { onSuccess: volver },
    );
  }

  function irARegistroLote() {
    const alcance: RegistroLoteAlcanceTorneo = { torneoId, volverA: `/torneo-admin/torneos/${torneoId}/plantillas` };
    navigate("/torneo-admin/plantillas/lote", { state: alcance });
  }

  if (modo.tipo === "crear") {
    return (
      <div>
        <h2>Nuevo vínculo — {torneoContexto}</h2>
        <ResourceForm
          fields={[
            {
              name: "jugador_id",
              label: "Jugador",
              type: "reference",
              required: true,
              optionsLoading: jugadores.listQuery.isLoading,
              options: (jugadores.listQuery.data ?? []).map((j) => ({ value: j.id, label: j.nombre })),
            },
            {
              name: "inscripcion_torneo_id",
              label: "Equipo",
              type: "reference",
              required: true,
              optionsLoading: inscripciones.listQuery.isLoading || equipos.listQuery.isLoading,
              options: (inscripciones.listQuery.data ?? []).map((i) => ({
                value: i.id,
                label: nombreEquipoDeInscripcion(i.id),
              })),
            },
            { name: "dorsal", label: "Dorsal", type: "number" },
            { name: "fecha_inicio", label: "Fecha de inicio", type: "date", required: true },
          ]}
          onSubmit={crearVinculo}
          submitting={resolviendoPerfil || crud.create.isPending}
          submitError={errorPerfil ?? (crud.create.isError ? apiErrorMessage(crud.create.error) : null)}
          submitLabel="Vincular"
          onCancel={volver}
        />
      </div>
    );
  }

  if (modo.tipo === "editar") {
    const initialValues: Record<string, ResourceFieldValue> = { dorsal: modo.fila.dorsal, estado: modo.fila.estado };
    return (
      <div>
        <h2>Editar vínculo</h2>
        <p className="muted">
          {etiquetaJugador(modo.fila.jugador_perfil_id)} en {nombreEquipoDeInscripcion(modo.fila.inscripcion_torneo_id)}
        </p>
        <ResourceForm
          fields={[
            { name: "dorsal", label: "Dorsal", type: "number" },
            { name: "estado", label: "Estado", type: "select", choices: ["Activo", "Inactivo", "Suspendido"] },
          ]}
          initialValues={initialValues}
          onSubmit={(values) => crud.update.mutate({ id: modo.fila.id, body: values as never }, { onSuccess: volver })}
          submitting={crud.update.isPending}
          submitError={crud.update.isError ? apiErrorMessage(crud.update.error) : null}
          submitLabel="Guardar cambios"
          onCancel={volver}
        />
      </div>
    );
  }

  if (modo.tipo === "baja") {
    return (
      <div>
        <h2>Dar de baja</h2>
        <p className="muted">
          {etiquetaJugador(modo.fila.jugador_perfil_id)} sale de {nombreEquipoDeInscripcion(modo.fila.inscripcion_torneo_id)} —
          libera el dorsal para otro jugador.
        </p>
        <ResourceForm
          fields={[{ name: "fecha_fin", label: "Fecha de baja", type: "date", required: true }]}
          onSubmit={(values) =>
            crud.customAction.mutate(
              { path: `/api/v1/plantillas/${modo.fila.id}/baja`, query: { fecha_fin: values.fecha_fin } },
              { onSuccess: volver },
            )
          }
          submitting={crud.customAction.isPending}
          submitError={crud.customAction.isError ? apiErrorMessage(crud.customAction.error) : null}
          submitLabel="Confirmar baja"
          onCancel={volver}
        />
      </div>
    );
  }

  const cargando =
    crud.listQuery.isLoading || jugadores.listQuery.isLoading || perfiles.listQuery.isLoading || inscripciones.listQuery.isLoading;

  return (
    <div>
      <div className="page__header">
        <h2>Plantillas de esta edición</h2>
        <div>
          <button type="button" onClick={() => setModo({ tipo: "crear" })}>
            + Nuevo vínculo
          </button>{" "}
          <button type="button" onClick={irARegistroLote}>
            + Registro por lote
          </button>
        </div>
      </div>

      {cargando && <p>Cargando...</p>}
      {/* 3A-5: LIMITE_LISTA es sobre los vínculos (crud), no sobre los
          equipos agrupados — un torneo con muchos equipos chicos puede
          tocar el techo aunque `gruposPorEquipo.length` sea bajo. */}
      {crud.truncado && (
        <p className="muted">Mostrando los primeros {LIMITE_LISTA} vínculos jugador-equipo de esta edición.</p>
      )}
      {!cargando && gruposPorEquipo.length === 0 && (
        <p className="muted">
          Todavía no hay equipos matriculados en este torneo. <Link to={`/torneo-admin/torneos/${torneoId}/equipos`}>Ir a Equipos</Link>
        </p>
      )}

      {gruposPorEquipo.map((grupo) => (
        <section key={grupo.inscripcionId} className="grid-plantillas__equipo">
          <h3>
            {iconoTorneo && <span aria-hidden="true">{iconoTorneo} </span>}
            {grupo.equipoNombre} ({grupo.activos} jugador{grupo.activos === 1 ? "" : "es"})
          </h3>
          {grupo.vinculos.length === 0 ? (
            <p className="muted">
              Sin jugadores todavía —{" "}
              <Link to={`/torneo-admin/torneos/${torneoId}/equipos`}>Ir a Equipos para agregar</Link>
            </p>
          ) : (
            <div className="grid-plantillas__jugadores">
              {grupo.vinculos.map((v) => {
                const jugador = jugadorDeVinculo(v.jugador_perfil_id);
                return (
                  <div key={v.id} className="tarjeta-jugador">
                    <button
                      type="button"
                      className="tarjeta-jugador__cuerpo"
                      onClick={() => jugador && setPerfilAbierto(jugador.id)}
                    >
                      <AvatarJugador
                        jugadorId={jugador?.id ?? v.jugador_perfil_id}
                        nombre={jugador?.nombre ?? etiquetaJugador(v.jugador_perfil_id)}
                        fotoUrl={jugador?.foto_url}
                      />
                      <span className="tarjeta-jugador__dorsal">{v.dorsal != null ? `#${v.dorsal}` : "—"}</span>
                      <span className="tarjeta-jugador__nombre">{jugador?.nombre ?? etiquetaJugador(v.jugador_perfil_id)}</span>
                      {v.estado !== "Activo" && <span className="badge badge--suspendido">{v.estado}</span>}
                    </button>
                    <div className="tarjeta-jugador__acciones">
                      <button type="button" className="link-button" onClick={() => setModo({ tipo: "editar", fila: v })}>
                        Editar vínculo
                      </button>
                      <button type="button" className="link-button" onClick={() => setModo({ tipo: "baja", fila: v })}>
                        Dar de baja
                      </button>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </section>
      ))}

      {perfilAbierto != null && (
        <ModalPerfilJugador jugadorId={perfilAbierto} onClose={() => setPerfilAbierto(null)} />
      )}
    </div>
  );
}
