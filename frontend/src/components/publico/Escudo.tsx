import { useState } from "react";
import { colorAvatar, inicialesJugador } from "../../pages/torneo-admin/avatarUtils";

interface EscudoProps {
  id: number;
  nombre: string;
  logoUrl: string | null | undefined;
  tamano?: "chico" | "mediano" | "grande";
}

/** Escudo de equipo o logo de torneo/disciplina para el portal público
 * (portal-publico-feed-partidos-plan.md, D14a): mismo patrón monocromo de
 * iniciales que `AvatarJugador.tsx` — NO el emoji de disciplina, que tiene
 * un peso óptico incompatible con un escudo PNG real y renderiza distinto
 * en Windows/Android/iOS. `onError` cubre tanto un `Logo_URL` que no
 * carga como uno que la validación de escritura (E-S2) no atrapó. */
export function Escudo(props: EscudoProps) {
  const { id, nombre, logoUrl, tamano = "chico" } = props;
  const [rota, setRota] = useState(false);
  const clase = `escudo escudo--${tamano}`;

  if (logoUrl && !rota) {
    return (
      <img
        className={clase}
        src={logoUrl}
        alt={nombre}
        onError={() => setRota(true)}
        // E-S2: un Logo_URL de tercero en una página pública no debe
        // filtrar el Referer de cada visitante anónimo al host que el
        // admin pegó.
        referrerPolicy="no-referrer"
      />
    );
  }
  return (
    <div className={clase} style={{ backgroundColor: colorAvatar(id) }} aria-hidden="true">
      {inicialesJugador(nombre)}
    </div>
  );
}
