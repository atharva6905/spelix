import type { ReactNode } from "react";

interface Props {
  children: ReactNode;
  as?: "h1" | "h2";
  variant?: "light" | "dark";
  className?: string;
}

export default function SectionHeading({
  children,
  as: Tag = "h2",
  variant = "light",
  className = "",
}: Props) {
  const color = variant === "dark" ? "text-ink-on-dark" : "text-ink-primary";
  const size =
    Tag === "h1"
      ? "text-[36px] leading-[1.0] md:text-[56px]"
      : "text-[28px] leading-[1.1] md:text-[40px] md:leading-[44px]";
  return (
    <Tag
      className={`font-display font-normal tracking-[-0.03em] ${size} ${color} ${className}`}
    >
      {children}
    </Tag>
  );
}
