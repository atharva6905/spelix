import { type FormEvent, useEffect, useRef, useState } from "react";
import {
  type BetaRequestSource,
  requestBetaAccess,
} from "@/api/beta";
import { isApiError } from "@/api/errors";

type Status = "idle" | "submitting" | "success" | "error-409" | "error";

interface LandingEmailFormProps {
  source: BetaRequestSource;
  size?: "full" | "compact";
}

export default function LandingEmailForm({
  source,
  size = "full",
}: LandingEmailFormProps) {
  const [email, setEmail] = useState("");
  const [status, setStatus] = useState<Status>("idle");
  const timerRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    return () => {
      if (timerRef.current) clearTimeout(timerRef.current);
    };
  }, []);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (status === "submitting" || status === "success") return;

    setStatus("submitting");

    try {
      await requestBetaAccess({ email, source, consented: true });
      setEmail("");
      setStatus("success");
    } catch (err: unknown) {
      if (isApiError(err) && err.status === 409) {
        setEmail("");
        setStatus("error-409");
      } else {
        setStatus("error");
      }

      timerRef.current = setTimeout(() => {
        setStatus("idle");
      }, 3500);
    }
  };

  const compact = size === "compact";

  const inputClasses = [
    "flex-1 bg-transparent border border-landing-border-vis text-landing-text rounded-[2px] font-display font-normal",
    "placeholder:text-[#6a5e52]",
    "focus:outline-none focus:border-[rgba(213,255,69,0.4)] focus:shadow-[0_0_0_3px_rgba(213,255,69,0.06)]",
    "transition-[border-color,box-shadow] duration-200 ease-in-out",
    compact
      ? "h-[38px] px-4 text-[13.5px] max-w-[280px]"
      : "h-[46px] px-4 text-[14.5px]",
  ].join(" ");

  const buttonClasses = [
    "bg-brand-primary text-[#141210] border-0 rounded-[2px] font-landing-mono font-semibold uppercase whitespace-nowrap",
    "hover:scale-[1.015] hover:opacity-88",
    "transition-[transform,opacity] duration-150 ease-in-out",
    "disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:scale-100",
    compact
      ? "h-[38px] px-4 text-[10px] tracking-[2px]"
      : "h-[46px] px-[22px] text-[11px] tracking-[2px]",
  ].join(" ");

  const buttonLabel = () => {
    switch (status) {
      case "submitting":
        return "Sending…";
      case "success":
        return "You’re on the list ✓";
      case "error-409":
        return "You’re already on the list";
      case "error":
        return "Something went wrong — try again";
      default:
        return compact ? (
          <>
            Request <span className="ml-1.5 inline-block -translate-y-px">&rarr;</span>
          </>
        ) : (
          <>
            Request Access{" "}
            <span className="ml-1.5 inline-block -translate-y-px">&rarr;</span>
          </>
        );
    }
  };

  const placeholder =
    status === "success"
      ? "We’ll reach out with your invite"
      : "your@email.com";

  return (
    <form
      onSubmit={handleSubmit}
      className="flex gap-2"
      style={compact ? { flex: 1, maxWidth: 480 } : { maxWidth: 460 }}
    >
      <input
        type="email"
        required
        aria-label="Email"
        placeholder={placeholder}
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        readOnly={status === "success"}
        className={inputClasses}
      />
      <button
        type="submit"
        disabled={status === "submitting"}
        className={buttonClasses}
      >
        {buttonLabel()}
      </button>
    </form>
  );
}
