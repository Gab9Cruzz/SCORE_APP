import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props {
  children: ReactNode;
  /** Qué falló, en palabras del usuario ("esta página", "el panel de mesa"). */
  ambito?: string;
  /** Al cambiar (p. ej. la ruta), el error se olvida y se vuelve a intentar:
   * sin esto, navegar a otra página seguiría mostrando el aviso. */
  claveReinicio?: unknown;
  /** Dentro de una página que ya tiene su h1 (el panel de mesa), h2. */
  anidado?: boolean;
}

interface State {
  error: Error | null;
  clave: unknown;
}

/** TASK-041 (FE-03): un error de render dejaba la pantalla en blanco, barra
 * de navegación incluida. Esto lo contiene: muestra qué pasó, deja seguir
 * navegando y ofrece reintentar o recargar.
 *
 * Tiene que ser de clase: React no tiene un equivalente con hooks para
 * `componentDidCatch`. */
export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, clave: this.props.claveReinicio };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  static getDerivedStateFromProps(props: Props, state: State): Partial<State> | null {
    if (props.claveReinicio !== state.clave) return { error: null, clave: props.claveReinicio };
    return null;
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // Registro: hoy la consola; es el punto donde se enchufaría un
    // servicio de errores.
    console.error("[ErrorBoundary]", this.props.ambito ?? "página", error, info.componentStack);
  }

  render() {
    if (!this.state.error) return this.props.children;
    const ambito = this.props.ambito ?? "esta página";
    const Titulo = this.props.anidado ? "h2" : "h1";
    return (
      <div className={this.props.anidado ? "error-limite" : "page estado-acceso"} role="alert">
        <Titulo>Algo falló al mostrar {ambito}</Titulo>
        <p>
          No se perdió nada de lo que ya estaba guardado. Podés reintentar, recargar la página o seguir navegando
          desde el menú.
        </p>
        <p className="muted--cuerpo">Detalle técnico: {this.state.error.message}</p>
        <div className="error-limite__acciones">
          <button type="button" className="boton boton--primario" onClick={() => window.location.reload()}>
            Recargar
          </button>
          <button type="button" className="boton boton--secundario" onClick={() => this.setState({ error: null })}>
            Reintentar
          </button>
        </div>
      </div>
    );
  }
}
