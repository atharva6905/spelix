import type { ReactNode } from "react";

interface Props {
  id?: string;
  className?: string;
  variant?: "light" | "dark";
  children: ReactNode;
}

export default function SectionWrapper({
  id,
  className = "",
  variant = "light",
  children,
}: Props) {
  const bg =
    variant === "dark"
      ? "bg-surface-dark text-ink-on-dark"
      : "bg-surface-page text-ink-primary";
  return (
    <section
      id={id}
      className={`w-full ${bg} py-24 ${className}`}
    >
      <div className="mx-auto max-w-[1128px] px-6 md:px-12 lg:px-16">
        {children}
      </div>
    </section>
  );
}
