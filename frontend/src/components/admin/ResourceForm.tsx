import { useState, type FormEvent } from "react";

export type ResourceFieldValue = string | number | boolean | null;

export interface ResourceFormFieldOption {
  value: number;
  label: string;
}

export interface ResourceFormField {
  name: string;
  label: string;
  /** "reference": select con opciones cargadas de otro recurso (id
   * numérico). "select": select con una lista fija de strings (ej. un
   * Literal de estado) — no pide nada a la API. "checkbox": booleano
   * simple (ej. Ida_Vuelta del motor de formatos,
   * motor-formatos-plantillas-navegacion-plan.md) — sin opciones, `false`
   * por defecto si no viene en `initialValues`. */
  type: "text" | "number" | "date" | "datetime" | "password" | "reference" | "select" | "checkbox";
  required?: boolean;
  /** Solo para type "reference". */
  options?: ResourceFormFieldOption[];
  optionsLoading?: boolean;
  /** Solo para type "select". */
  choices?: string[];
}

interface ResourceFormProps {
  /** También puede ser una función de los valores actuales — para campos
   * condicionados entre sí (torneos-admin-plan.md, Fase 2: Modalidad solo
   * se muestra si la Disciplina elegida es "Individual"). Un array plano
   * sigue funcionando igual que antes para el resto de las páginas. */
  fields: ResourceFormField[] | ((values: Record<string, ResourceFieldValue>) => ResourceFormField[]);
  initialValues?: Record<string, ResourceFieldValue>;
  onSubmit: (values: Record<string, ResourceFieldValue>) => void;
  submitting: boolean;
  submitError: string | null;
  submitLabel?: string;
  onCancel?: () => void;
}

/** Form genérico de creación/edición para el módulo Torneo Admin
 * (roles-3-modulos-plan.md, Fase 2, D1). Mismo patrón de error inline
 * (`submitError`) que ControlDeMesa.tsx — se le pasa el resultado de
 * `apiErrorMessage(mutation.error)` desde afuera, este componente no sabe
 * nada de la API. */
export function ResourceForm(props: ResourceFormProps) {
  const {
    fields,
    initialValues,
    onSubmit,
    submitting,
    submitError,
    submitLabel = "Guardar",
    onCancel,
  } = props;

  const [values, setValues] = useState<Record<string, ResourceFieldValue>>(() => initialValues ?? {});

  const resolvedFields = typeof fields === "function" ? fields(values) : fields;

  function setField(name: string, value: ResourceFieldValue) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  const puedeEnviar = resolvedFields.every((f) => {
    if (!f.required) return true;
    const v = values[f.name];
    return v !== null && v !== undefined && v !== "";
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!puedeEnviar) return;
    // EC-24 (torneos-admin-plan.md): si un campo condicional dejó de estar
    // presente (ej. Modalidad al volver a una disciplina de tipo Equipo),
    // su valor viejo se filtra ACÁ, al mandar — no alcanza con ocultar el
    // input, o el submit mandaría un valor "fantasma" que el admin ya no
    // puede ver ni corregir en pantalla. Se filtra en vez de limpiar el
    // estado con un efecto: si el admin vuelve a la disciplina donde ese
    // campo sí aplica, recupera lo que había tipeado antes.
    const nombresVigentes = new Set(resolvedFields.map((f) => f.name));
    const valoresVigentes: Record<string, ResourceFieldValue> = {};
    for (const [k, v] of Object.entries(values)) if (nombresVigentes.has(k)) valoresVigentes[k] = v;
    onSubmit(valoresVigentes);
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit}>
      {resolvedFields.map((f) => {
        if (f.type === "reference") {
          return (
            <label key={f.name}>
              {f.label}
              <select
                value={(values[f.name] as string | number | null | undefined) ?? ""}
                onChange={(e) => setField(f.name, e.target.value ? Number(e.target.value) : null)}
                disabled={f.optionsLoading}
              >
                <option value="">{f.optionsLoading ? "Cargando..." : "Elegir..."}</option>
                {(f.options ?? []).map((o) => (
                  <option key={o.value} value={o.value}>
                    {o.label}
                  </option>
                ))}
              </select>
            </label>
          );
        }
        if (f.type === "select") {
          return (
            <label key={f.name}>
              {f.label}
              <select
                value={(values[f.name] as string | number | null | undefined) ?? ""}
                onChange={(e) => setField(f.name, e.target.value || null)}
              >
                <option value="">Elegir...</option>
                {(f.choices ?? []).map((c) => (
                  <option key={c} value={c}>
                    {c}
                  </option>
                ))}
              </select>
            </label>
          );
        }
        if (f.type === "checkbox") {
          return (
            <label key={f.name} className="resource-form__checkbox">
              <input
                type="checkbox"
                checked={Boolean(values[f.name])}
                onChange={(e) => setField(f.name, e.target.checked)}
              />
              {f.label}
            </label>
          );
        }
        const inputType = f.type === "datetime" ? "datetime-local" : f.type;
        return (
          <label key={f.name}>
            {f.label}
            <input
              type={inputType}
              value={(values[f.name] as string | number | null | undefined) ?? ""}
              onChange={(e) =>
                setField(f.name, f.type === "number" ? (e.target.value ? Number(e.target.value) : null) : e.target.value)
              }
            />
          </label>
        );
      })}
      {submitError && <p className="error-text">{submitError}</p>}
      <div className="resource-form__actions">
        {onCancel && (
          <button type="button" className="link-button" onClick={onCancel}>
            Cancelar
          </button>
        )}
        <button type="submit" disabled={!puedeEnviar || submitting}>
          {submitting ? "Guardando..." : submitLabel}
        </button>
      </div>
    </form>
  );
}
