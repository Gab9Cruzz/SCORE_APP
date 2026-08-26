import { useState, type FormEvent } from "react";

export type ResourceFieldValue = string | number | null;

export interface ResourceFormFieldOption {
  value: number;
  label: string;
}

export interface ResourceFormField {
  name: string;
  label: string;
  /** "reference": select con opciones cargadas de otro recurso (id
   * numérico). "select": select con una lista fija de strings (ej. un
   * Literal de estado) — no pide nada a la API. */
  type: "text" | "number" | "date" | "datetime" | "password" | "reference" | "select";
  required?: boolean;
  /** Solo para type "reference". */
  options?: ResourceFormFieldOption[];
  optionsLoading?: boolean;
  /** Solo para type "select". */
  choices?: string[];
}

interface ResourceFormProps {
  fields: ResourceFormField[];
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

  function setField(name: string, value: ResourceFieldValue) {
    setValues((v) => ({ ...v, [name]: value }));
  }

  const puedeEnviar = fields.every((f) => {
    if (!f.required) return true;
    const v = values[f.name];
    return v !== null && v !== undefined && v !== "";
  });

  function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!puedeEnviar) return;
    onSubmit(values);
  }

  return (
    <form className="resource-form" onSubmit={handleSubmit}>
      {fields.map((f) => {
        if (f.type === "reference") {
          return (
            <label key={f.name}>
              {f.label}
              <select
                value={values[f.name] ?? ""}
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
              <select value={values[f.name] ?? ""} onChange={(e) => setField(f.name, e.target.value || null)}>
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
        const inputType = f.type === "datetime" ? "datetime-local" : f.type;
        return (
          <label key={f.name}>
            {f.label}
            <input
              type={inputType}
              value={values[f.name] ?? ""}
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
