interface Props {
  children: string;
  variant?: "light" | "dark";
}

export default function SectionLabel({ children, variant = "light" }: Props) {
  const color = variant === "dark" ? "text-ink-on-dark-muted" : "text-ink-muted";
  return (
    <p
      className={`mb-4 flex items-center gap-2 font-sans text-sm leading-[1.3] ${color}`}
    >
      <span aria-hidden="true">◆</span>
      <span>{children}</span>
    </p>
  );
}
