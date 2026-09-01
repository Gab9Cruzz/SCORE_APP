import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";
import { server } from "../../test/msw-server";
import { createWrapper } from "../../test/test-utils";
import { EquiposAdminPage } from "./EquiposAdmin";

const mockNavigate = vi.fn();
vi.mock("react-router-dom", async (importOriginal) => {
  const actual = await importOriginal<typeof import("react-router-dom")>();
  return { ...actual, useNavigate: () => mockNavigate };
});

const EQUIPOS = "http://127.0.0.1:8000/api/v1/equipos";
const DISCIPLINAS = "http://127.0.0.1:8000/api/v1/disciplinas";
const MODALIDADES = "http://127.0.0.1:8000/api/v1/modalidades";

const DISCIPLINAS_FIXTURE = [
  { id: 1, nombre: "Fútbol", estado: "Activo" },
  { id: 2, nombre: "Tenis", estado: "Activo" },
];
const MODALIDADES_FIXTURE = [
  { id: 1, nombre: "Fútbol 11", disciplina_id: 1, tamano_equipo: 11, estado: "Activo" },
  { id: 2, nombre: "Fútbol 5", disciplina_id: 1, tamano_equipo: 5, estado: "Activo" },
  { id: 3, nombre: "Dobles", disciplina_id: 2, tamano_equipo: 2, estado: "Activo" },
];

interface EquipoFixture {
  id: number;
  nombre: string;
  disciplina_id: number;
  modalidad_id: number;
  plantilla_total: number;
  estado: string;
}

const TIGRES: EquipoFixture = {
  id: 1,
  nombre: "Los Tigres",
  disciplina_id: 1,
  modalidad_id: 1,
  plantilla_total: 14,
  estado: "Activo",
};
const NADAL: EquipoFixture = {
  id: 2,
  nombre: "Nadal/Alcaraz",
  disciplina_id: 2,
  modalidad_id: 3,
  plantilla_total: 2,
  estado: "Activo",
};
const VACIO: EquipoFixture = {
  id: 3,
  nombre: "Sin Nombre",
  disciplina_id: 1,
  modalidad_id: 2,
  plantilla_total: 0,
  estado: "Activo",
};

/** Los filtros de Disciplina/Categoría/Estado son SERVER-SIDE (Mejora #1):
 * el handler tiene que respetarlos o el test estaría verificando un filtro
 * que en producción no existe. */
function handlerEquipos(equipos: EquipoFixture[]) {
  return http.get(EQUIPOS, ({ request }) => {
    const url = new URL(request.url);
    const disciplinaId = url.searchParams.get("disciplina_id");
    const modalidadId = url.searchParams.get("modalidad_id");
    const estado = url.searchParams.get("estado");
    return HttpResponse.json(
      equipos.filter(
        (e) =>
          (disciplinaId === null || e.disciplina_id === Number(disciplinaId)) &&
          (modalidadId === null || e.modalidad_id === Number(modalidadId)) &&
          (estado === null || e.estado === estado),
      ),
    );
  });
}

function montar(equipos: EquipoFixture[]) {
  server.use(
    handlerEquipos(equipos),
    http.get(DISCIPLINAS, () => HttpResponse.json(DISCIPLINAS_FIXTURE)),
    http.get(MODALIDADES, () => HttpResponse.json(MODALIDADES_FIXTURE)),
  );
  const Wrapper = createWrapper();
  return render(
    <Wrapper>
      <EquiposAdminPage />
    </Wrapper>,
  );
}

describe("EquiposAdminPage", () => {
  // T11 — la grilla del pedido A: Nombre / Disciplina / Categoría /
  // Plantilla / Estado, con Disciplina y Categoría resueltas contra el
  // catálogo (columnas calculadas, no `row[key]` plano).
  it("muestra Disciplina, Categoría y Plantilla resueltas contra el catálogo", async () => {
    montar([TIGRES, NADAL]);

    expect(await screen.findByText("Los Tigres")).toBeInTheDocument();
    // Con el icono del módulo iconosDisciplina delante (Decisión #8).
    expect(screen.getByRole("cell", { name: "⚽ Fútbol" })).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Fútbol 11" })).toBeInTheDocument();
    expect(screen.getByText("14 jug.")).toBeInTheDocument();
    expect(screen.getByRole("cell", { name: "Dobles" })).toBeInTheDocument();
    expect(screen.getByText("2 jug.")).toBeInTheDocument();
  });

  // EC-39 — 0 jugadores es válido, pero el vacío ofrece la salida.
  // gestion-avanzada-equipos-control-mesa-plan.md (Flujo 1): el destino ya
  // no es el listado de torneos — es el Detalle del Equipo, que habilita
  // la Plantilla Base (D1-C) sin depender de ningún torneo.
  it("un equipo sin jugadores ofrece el camino para cargarlos", async () => {
    montar([VACIO]);
    const user = userEvent.setup();

    await user.click(await screen.findByRole("button", { name: "0 jug. — agregar" }));

    expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/equipos/3");
  });

  // T12 — el filtro pega contra el servidor y el empty-state filtrado NO
  // dice lo mismo que el vacío real (o el admin crea un duplicado).
  it("filtra por disciplina y distingue el vacío filtrado del vacío real", async () => {
    montar([TIGRES, NADAL]);
    const user = userEvent.setup();

    expect(await screen.findByText("Los Tigres")).toBeInTheDocument();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "2");

    expect(await screen.findByText("Nadal/Alcaraz")).toBeInTheDocument();
    expect(screen.queryByText("Los Tigres")).not.toBeInTheDocument();

    // Categoría de otra disciplina → cero resultados, pero es un vacío
    // FILTRADO: el mensaje lo dice y ofrece limpiar.
    await user.selectOptions(screen.getByLabelText("Disciplina"), "1");
    await user.selectOptions(screen.getByLabelText("Categoría"), "2");
    expect(await screen.findByText(/Ningún equipo coincide con estos filtros/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Limpiar filtros" }));
    expect(await screen.findByText("Los Tigres")).toBeInTheDocument();
  });

  it("el vacío real no habla de filtros", async () => {
    montar([]);
    expect(await screen.findByText("No hay equipos creados todavía.")).toBeInTheDocument();
  });

  // Pedido A: "el formulario debe exigir la Disciplina", y la Categoría
  // depende de ella.
  it("el formulario exige Disciplina y filtra Categoría por la disciplina elegida", async () => {
    montar([]);
    const user = userEvent.setup();
    let bodyRecibido: unknown;
    server.use(
      http.post(EQUIPOS, async ({ request }) => {
        bodyRecibido = await request.json();
        return HttpResponse.json({ ...TIGRES, id: 9 }, { status: 201 });
      }),
    );

    await user.click(await screen.findByRole("button", { name: "+ Nuevo equipo" }));
    await user.type(screen.getByLabelText("Nombre"), "Equipo Nuevo");

    // Sin disciplina elegida, Categoría no ofrece nada: el select arranca
    // vacío en vez de mostrar las 66 modalidades del catálogo.
    const categoria = screen.getByLabelText("Categoría (modalidad)");
    expect(categoria.querySelectorAll("option")).toHaveLength(1); // solo "Elegir..."
    expect(screen.getByRole("button", { name: "Crear" })).toBeDisabled();

    await user.selectOptions(screen.getByLabelText("Disciplina"), "1");
    expect(categoria.querySelectorAll("option")).toHaveLength(3); // "Elegir..." + Fútbol 11 + Fútbol 5

    await user.selectOptions(categoria, "1");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() =>
      expect(bodyRecibido).toEqual({ nombre: "Equipo Nuevo", disciplina_id: 1, modalidad_id: 1 }),
    );
  });

  // gestion-avanzada-equipos-control-mesa-plan.md (Flujo 1): la creación
  // redirige derecho al Detalle del Equipo, que es donde ahora se carga
  // la Plantilla Base de inmediato — reemplaza la nota "se carga al
  // inscribir a un torneo", que dejó de ser cierta con D1-C.
  it("redirige al Detalle del Equipo tras crear uno nuevo", async () => {
    montar([]);
    const user = userEvent.setup();
    server.use(
      http.post(EQUIPOS, async () => HttpResponse.json({ ...TIGRES, id: 9 }, { status: 201 })),
    );

    await user.click(await screen.findByRole("button", { name: "+ Nuevo equipo" }));
    await user.type(screen.getByLabelText("Nombre"), "Equipo Nuevo");
    await user.selectOptions(screen.getByLabelText("Disciplina"), "1");
    await user.selectOptions(screen.getByLabelText("Categoría (modalidad)"), "1");
    await user.click(screen.getByRole("button", { name: "Crear" }));

    await waitFor(() => expect(mockNavigate).toHaveBeenCalledWith("/torneo-admin/equipos/9"));
  });
});
