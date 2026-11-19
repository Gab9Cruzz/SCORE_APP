import { useId, type ReactNode } from "react";

/** Lo que el campo le pasa a su control: id para la etiqueta, la
 * descripción (ayuda y error) y la clase con el borde de DESIGN.md. */
export interface PropsControl {
  id: string;
  className: string;
  "aria-describedby"?: string;
  "aria-invalid"?: true;
}

interface FieldProps {
  etiqueta: ReactNode;
  /** Mensaje de error del campo; marca el control con aria-invalid. */
  error?: string | null;
  /** Texto de ayuda bajo el control (formato esperado, restricciones). */
  ayuda?: ReactNode;
  /** El control (input, select, textarea) con las props ya puestas:
   * `{(p) => <input {...p} value=... />}`. Una función y no un hijo
   * suelto, para no clonar elementos ni adivinar cuál es el control. */
  children: (control: PropsControl) => ReactNode;
}

/** Campo de formulario base (TASK-034): etiqueta asociada por id, ayuda y
 * error enlazados con aria-describedby. Ver DESIGN.md, "Campos". */
export function Field({ etiqueta, error, ayuda, children }: FieldProps) {
  const id = useId();
  const idAyuda = `${id}-ayuda`;
  const idError = `${id}-error`;
  const descripcion = [ayuda ? idAyuda : null, error ? idError : null].filter(Boolean).join(" ");

  const control: PropsControl = { id, className: "campo__control" };
  if (descripcion) control["aria-describedby"] = descripcion;
  if (error) control["aria-invalid"] = true;

  return (
    <div className="campo">
      <label htmlFor={id} className="campo__etiqueta">
        {etiqueta}
      </label>
      {children(control)}
      {ayuda && (
        <p id={idAyuda} className="campo__ayuda">
          {ayuda}
        </p>
      )}
      {error && (
        <p id={idError} className="campo__error">
          {error}
        </p>
      )}
    </div>
  );
}
