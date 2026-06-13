import type { ReactNode } from "react";

interface FieldErrorProps {
  /** The error message. When falsy, nothing renders. */
  children?: ReactNode;
  /** Extra classes merged onto the normalized base (e.g. `mt-1`). */
  className?: string;
}

/**
 * Shared inline field-error (issue #236). Renders the error text with a single
 * normalized styling (`text-sm text-red-600`) and `role="alert"` so assistive
 * tech announces it consistently. Replaces the divergent inline error sites
 * across the upload forms (some of which previously omitted `role="alert"`).
 */
export function FieldError({ children, className }: FieldErrorProps) {
  if (!children) {
    return null;
  }

  return (
    <p
      role="alert"
      className={["text-sm text-red-600", className].filter(Boolean).join(" ")}
    >
      {children}
    </p>
  );
}
