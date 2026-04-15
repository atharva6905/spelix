import { useId, useState, type ReactNode } from "react";

interface Props {
  title: string;
  children: ReactNode;
  defaultOpen?: boolean;
}

export default function AccordionItem({ title, children, defaultOpen = false }: Props) {
  const [open, setOpen] = useState(defaultOpen);
  const bodyId = useId();

  return (
    <div className="border-b border-border-subtle">
      <button
        type="button"
        className="flex w-full items-center justify-between py-6 text-left font-display text-xl leading-tight tracking-[-0.02em]"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        aria-controls={bodyId}
      >
        <span>{title}</span>
        <span
          aria-hidden="true"
          className={`ml-4 inline-block h-3 w-3 rounded-full transition-colors ${
            open ? "bg-brand-primary" : "bg-ink-muted"
          }`}
        />
      </button>
      {open && (
        <div id={bodyId} className="pb-6 font-sans text-base text-ink-primary">
          {children}
        </div>
      )}
    </div>
  );
}
