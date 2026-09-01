import { useEffect, useState } from "react";

/** 3B-1 (docs/plans/cierre-backlog-todos-plan.md): estado de conexión del
 * navegador — `navigator.onLine` + los eventos `online`/`offline` de
 * `window`. Es un indicador de "el navegador cree que hay red", no una
 * confirmación de que el backend responde (podría estar caído con
 * `onLine === true` igual) — para eso está el propio error de la
 * request, esto solo cubre el caso más común de Control de Mesa: wifi de
 * cancha que se corta y vuelve. */
export function useOnlineStatus(): boolean {
  const [online, setOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));

  useEffect(() => {
    const marcarOnline = () => setOnline(true);
    const marcarOffline = () => setOnline(false);
    window.addEventListener("online", marcarOnline);
    window.addEventListener("offline", marcarOffline);
    return () => {
      window.removeEventListener("online", marcarOnline);
      window.removeEventListener("offline", marcarOffline);
    };
  }, []);

  return online;
}
