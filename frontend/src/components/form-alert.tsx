import { CircleAlert } from "lucide-react";

/** Form-level error, announced to assistive technology as soon as it appears. */
export function FormAlert({ message }: { message: string | null }) {
  if (!message) return null;
  return (
    <div
      role="alert"
      className="flex items-start gap-2.5 rounded-lg border border-destructive/30 bg-destructive/10 px-3.5 py-3 text-sm text-destructive-foreground animate-fade"
    >
      <CircleAlert className="mt-0.5 size-4 shrink-0 text-destructive" aria-hidden="true" />
      <p>{message}</p>
    </div>
  );
}
