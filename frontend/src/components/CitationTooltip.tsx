import type { ReactNode } from "react";
import type { Citation } from "@/api/analyses";
import { DoiLink } from "@/components/DoiLink";

interface CitationTooltipProps {
  index: number;
  citation: Citation;
}

/**
 * Inline citation marker with hover/focus tooltip showing source metadata.
 * Renders as a superscript [N] button — keyboard-accessible via focus.
 */
export function CitationTooltip({ index, citation }: CitationTooltipProps) {
  return (
    <span className="group relative inline-block">
      <button
        type="button"
        data-testid={`citation-marker-${index}`}
        aria-label={`Citation ${index}`}
        className="cursor-pointer align-super text-xs font-semibold text-blue-600 hover:text-blue-800 focus:text-blue-800 focus:outline-none"
      >
        [{index}]
      </button>
      <span
        data-testid={`citation-tooltip-panel-${index}`}
        role="tooltip"
        className="pointer-events-none invisible absolute bottom-full left-1/2 z-10 mb-1 w-64 max-w-[90vw] -translate-x-1/2 rounded-md border border-gray-200 bg-white p-3 text-left text-xs shadow-lg group-hover:pointer-events-auto group-hover:visible group-focus-within:pointer-events-auto group-focus-within:visible"
      >
        <p className="mb-1 font-medium text-gray-900">{citation.title}</p>
        <p className="text-gray-600">
          {citation.authors.join(", ")} ({citation.year})
        </p>
        {citation.doi && (
          <DoiLink
            doi={citation.doi}
            className="mt-1 inline-block text-blue-600"
            aria-label="DOI link"
          >
            DOI: {citation.doi}
          </DoiLink>
        )}
      </span>
    </span>
  );
}

/**
 * Parse text containing [N] citation markers and return ReactNode array
 * with CitationTooltip components for valid references.
 *
 * Citations are 1-based: [1] maps to citations[0].
 * Out-of-range or [0] markers render as plain text.
 */
export function parseWithCitations(
  text: string,
  citations: Citation[],
): ReactNode[] {
  if (!text) return [];

  const parts: ReactNode[] = [];
  const regex = /\[(\d+)\]/g;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = regex.exec(text)) !== null) {
    // Text before the match
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }

    const citationIndex = parseInt(match[1], 10);

    if (citationIndex >= 1 && citationIndex <= citations.length) {
      parts.push(
        <CitationTooltip
          key={`${match.index}-${citationIndex}`}
          index={citationIndex}
          citation={citations[citationIndex - 1]}
        />,
      );
    } else {
      // Out-of-range: render as plain text
      parts.push(match[0]);
    }

    lastIndex = match.index + match[0].length;
  }

  // Remaining text after last match
  if (lastIndex < text.length) {
    parts.push(text.slice(lastIndex));
  }

  return parts;
}
