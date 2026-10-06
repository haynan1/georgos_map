import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { PASSWORD_MIN } from "./schemas";

/** Live length feedback. Length is what matters (NIST SP 800-63B): no composition rules. */
export function PasswordHint({ value }: { value: string }) {
  const met = value.length >= PASSWORD_MIN;
  return (
    <span
      className={cn("inline-flex items-center gap-1.5 transition-colors", met && "text-success")}
    >
      <Check className={cn("size-3.5", !met && "opacity-40")} aria-hidden="true" />
      Pelo menos {PASSWORD_MIN} caracteres
      <span className="tabular text-subtle-foreground" aria-hidden="true">
        · {value.length}
      </span>
    </span>
  );
}
