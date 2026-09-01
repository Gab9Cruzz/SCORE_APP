import type { components } from "./schema";

/**
 * Alias de los tipos YA generados por `schema.d.ts` (openapi-typescript,
 * ver ese archivo) para las formas de fila que más se repiten a mano por
 * el frontend (3A-6, docs/plans/cierre-backlog-todos-plan.md).
 *
 * Antes de este módulo, 8 archivos declaraban su propio `interface
 * EquipoRow { id; nombre; ... }` (un subset ad-hoc de los campos que
 * usaban) y otros 4 su propio `interface ModalidadRow` — si `EquipoOut`
 * gana o pierde un campo en el backend, `schema.d.ts` se regenera pero
 * esas 12 declaraciones sueltas no se enteran hasta que alguien lo nota a
 * mano. Un solo alias acá significa que agregar/sacar un campo en el
 * backend rompe la build en el momento (import roto o campo faltante),
 * no en producción.
 *
 * A propósito son alias de la forma COMPLETA (`EquipoOut`/`ModalidadOut`),
 * no un subset recortado por caso de uso — cada archivo seguía leyendo
 * solo los campos que necesitaba, TypeScript estructural no exige usar
 * todos. Mismo criterio que AuditoriaAdmin.tsx ya usaba para su propio
 * tipo (`components["schemas"]["AuditoriaOut"]` directo, sin alias local).
 */
export type Equipo = components["schemas"]["EquipoOut"];
export type Modalidad = components["schemas"]["ModalidadOut"];
