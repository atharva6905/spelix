import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";

export default function BetaTermsPage() {
  const [markdown, setMarkdown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    fetch("/beta-terms.md")
      .then((resp) => {
        if (!resp.ok) throw new Error("Could not load beta terms");
        return resp.text();
      })
      .then((text) => {
        if (!cancelled) setMarkdown(text);
      })
      .catch(() => {
        if (!cancelled) setError("Could not load beta terms");
      });

    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <main className="min-h-screen bg-surface-page py-24">
      <article className="prose mx-auto max-w-[720px] px-6 font-sans text-ink-primary">
        {error ? (
          <p role="alert">{error}</p>
        ) : markdown ? (
          <ReactMarkdown>{markdown}</ReactMarkdown>
        ) : (
          <p className="text-ink-muted">Loading…</p>
        )}
      </article>
    </main>
  );
}
