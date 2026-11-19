import { useEffect, useState } from "react";

/** Página actual de una grilla (TASK-039), que vuelve a 0 sola cuando
 * cambian los filtros: `clave` resume los filtros vigentes, y una página
 * guardada con otra clave ya no vale (la página 4 de "todos" no existe en
 * "solo Inactivos"). Se deriva en el render, sin efecto, así no hay un
 * pedido intermedio a la página vieja con los filtros nuevos. */
export function usePagina(clave: string): [number, (pagina: number) => void] {
  const [estado, setEstado] = useState({ clave, pagina: 0 });
  const pagina = estado.clave === clave ? estado.pagina : 0;
  return [pagina, (p: number) => setEstado({ clave, pagina: p })];
}

/** `valor` con un retardo: cambia recién cuando deja de cambiar durante
 * `ms`. Para no pedirle al servidor una búsqueda por cada tecla. */
export function useValorConRetardo<T>(valor: T, ms = 300): T {
  const [diferido, setDiferido] = useState(valor);
  useEffect(() => {
    const t = setTimeout(() => setDiferido(valor), ms);
    return () => clearTimeout(t);
  }, [valor, ms]);
  return diferido;
}
