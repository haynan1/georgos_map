import type { AnyFieldApi, AnyFormApi } from "@tanstack/react-form";
import type { ChangeEvent, ReactNode } from "react";
import { Field, FieldDescription, FieldError, FieldLabel } from "@/components/ui/field";
import { ApiError } from "@/lib/api/client";

export interface ControlProps {
  id: string;
  name: string;
  value: string;
  onBlur: () => void;
  onChange: (event: ChangeEvent<HTMLInputElement>) => void;
  "aria-invalid": boolean;
  "aria-describedby": string | undefined;
}

interface FormFieldProps {
  field: AnyFieldApi;
  label: ReactNode;
  description?: ReactNode;
  children: (control: ControlProps) => ReactNode;
}

/**
 * Binds a TanStack Form field to shadcn's accessible Field primitives.
 *
 * Validation runs on every change, but errors only surface after the user leaves the
 * field or tries to submit — never mid-typing.
 */
export function FormField({ field, label, description, children }: FormFieldProps) {
  const { meta } = field.state;
  const attempted = field.form.state.submissionAttempts > 0;
  const invalid = (meta.isBlurred || attempted) && !meta.isValid;
  const id = `field-${field.name}`;
  const errorId = `${id}-error`;
  const descriptionId = `${id}-description`;
  const describedBy = invalid ? errorId : description ? descriptionId : undefined;

  return (
    <Field data-invalid={invalid}>
      <FieldLabel htmlFor={id}>{label}</FieldLabel>
      {children({
        id,
        name: field.name,
        value: field.state.value as string,
        onBlur: field.handleBlur,
        onChange: (event) => {
          // A server-side error describes the value that was submitted; editing clears it.
          if (meta.errorMap.onServer) {
            field.setMeta((prev) => ({
              ...prev,
              errorMap: { ...prev.errorMap, onServer: undefined },
            }));
          }
          field.handleChange(event.target.value);
        },
        "aria-invalid": invalid,
        "aria-describedby": describedBy,
      })}
      {description && !invalid && (
        <FieldDescription id={descriptionId}>{description}</FieldDescription>
      )}
      {invalid && <FieldError id={errorId} errors={meta.errors.map(toIssue)} />}
    </Field>
  );
}

function toIssue(error: unknown): { message?: string } | undefined {
  if (typeof error === "string") return { message: error };
  if (typeof error === "object" && error !== null && "message" in error) {
    return { message: String(error.message) };
  }
  return undefined;
}

/**
 * Attach API validation errors (``loc: ["body", "<field>"]``) to the matching fields.
 * Returns false when the error is not field-specific, so the caller shows it globally.
 */
export function applyServerErrors(form: AnyFormApi, error: unknown): boolean {
  if (!(error instanceof ApiError) || error.fields.length === 0) return false;
  let applied = false;
  for (const issue of error.fields) {
    const name = issue.loc[1];
    if (!name || !(name in form.state.values)) continue;
    form.setFieldMeta(name, (meta) => ({
      ...meta,
      isBlurred: true,
      errorMap: { ...meta.errorMap, onServer: issue.message },
    }));
    applied = true;
  }
  if (applied) focusFirstInvalid();
  return applied;
}

/** After a failed submit, move focus to the first invalid field (WCAG 3.3.1). */
export function focusFirstInvalid() {
  requestAnimationFrame(() => {
    document.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus();
  });
}
