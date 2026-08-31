import { useState } from "react";
import { colorAvatar, inicialesJugador } from "./avatarUtils";

interface AvatarJugadorProps {
  jugadorId: number;
  nombre: string;
  fotoUrl: string | null | undefined;
  tamano?: "chico" | "grande";
}

/** Foto si hay `Foto_URL`, iniciales en un círculo de color determinístico
 * si no — usado por el grid de Plantillas y el modal de Perfil (Design
 * sección D, motor-formatos-plantillas-navegacion-plan.md). Sin uploader
 * en este plan: si la URL guardada no carga, cae a iniciales en vez del
 * ícono de imagen rota del navegador. */
export function AvatarJugador(props: AvatarJugadorProps) {
  const { jugadorId, nombre, fotoUrl, tamano = "chico" } = props;
  const [rota, setRota] = useState(false);
  const clase = `avatar-jugador avatar-jugador--${tamano}`;

  if (fotoUrl && !rota) {
    return <img className={clase} src={fotoUrl} alt={nombre} onError={() => setRota(true)} />;
  }
  return (
    <div className={clase} style={{ backgroundColor: colorAvatar(jugadorId) }} aria-hidden="true">
      {inicialesJugador(nombre)}
    </div>
  );
}
