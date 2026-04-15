interface Props {
  variant?: "light" | "dark";
  withLink?: boolean;
  className?: string;
}

export default function BetaDisclaimer({
  variant = "light",
  withLink = true,
  className = "",
}: Props) {
  const color = variant === "dark" ? "text-ink-on-dark-muted" : "text-ink-muted";
  return (
    <p className={`font-sans text-xs leading-relaxed ${color} ${className}`}>
      Spelix is currently in private beta. This feedback is for educational and
      performance purposes only. It is not a substitute for advice from a
      qualified coach, physiotherapist, or medical professional.
      {withLink && (
        <>
          {" "}
          <a href="/beta-terms" className="underline">
            Read beta terms →
          </a>
        </>
      )}
    </p>
  );
}
