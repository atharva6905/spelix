import type { ReactNode } from "react";

interface DoiLinkProps {
  doi?: string | null;
  /** Extra classes merged onto the base `hover:underline` (e.g. `font-mono text-xs`). */
  className?: string;
  "aria-label"?: string;
  /** Custom link label; defaults to the DOI itself. */
  children?: ReactNode;
}

/**
 * Shared DOI resolver link (issue #232). Renders an anchor to
 * `https://doi.org/{doi}` with the security-relevant `target`/`rel`
 * attributes in one place, or a standardized em-dash fallback when
 * no DOI is present.
 */
export function DoiLink({
  doi,
  className,
  "aria-label": ariaLabel,
  children,
}: DoiLinkProps) {
  if (!doi) {
    return (
      <span data-testid="doi-empty" className="text-gray-400">
        —
      </span>
    );
  }

  return (
    <a
      href={`https://doi.org/${doi}`}
      target="_blank"
      rel="noopener noreferrer"
      className={["hover:underline", className].filter(Boolean).join(" ")}
      aria-label={ariaLabel}
    >
      {children ?? doi}
    </a>
  );
}
