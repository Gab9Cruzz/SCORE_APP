import type { ButtonHTMLAttributes, Ref } from "react";

/** Las cuatro clases de botón de DESIGN.md (TASK-034).
 *
 * - `primario`: la acción principal de la pantalla o del formulario. Una
 *   sola por zona.
 * - `secundario`: acciones frecuentes que no son la principal (Editar).
 * - `peligro`: acciones destructivas (Confirmar una baja).
 * - `enlace`: salir sin hacer nada (Cancelar, Volver) o navegar.
 */
export type VarianteBoton = "primario" | "secundario" | "peligro" | "enlace";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variante?: VarianteBoton;
  ref?: Ref<HTMLButtonElement>;
}

/** Botón base. `type` vale "button" por defecto: un `<button>` suelto
 * dentro de un `<form>` es "submit" y envía el formulario sin querer.
 *
 * `enlace` también lleva la clase vieja `link-button` para que sigan
 * valiendo las reglas por contexto que ya existen (`.mesa .link-button`,
 * `.filtros-recurso .link-button`). */
export function Button({ variante = "secundario", type = "button", className, ref, ...resto }: ButtonProps) {
  const clases = ["boton", `boton--${variante}`];
  if (variante === "enlace") clases.push("link-button");
  if (className) clases.push(className);
  return <button ref={ref} type={type} className={clases.join(" ")} {...resto} />;
}
