import { useId, useState, type FormEvent } from "react";
import { requestBetaAccess, type BetaRequestSource } from "@/api/beta";
import { isApiError } from "@/api/errors";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

interface Props {
  source: BetaRequestSource;
  buttonLabel?: string;
  microCopy?: string;
  /** Fires on successful submission — used for PostHog + parent UI state. */
  onSuccess?: (email: string) => void;
  /** Fires on submit attempt regardless of outcome — for PostHog attempt event. */
  onAttempt?: () => void;
  /** Fires on non-2xx or network error — for PostHog error event. */
  onError?: (status: number | null) => void;
}

type Status = "idle" | "submitting" | "success" | "error";

export default function EmailCaptureForm({
  source,
  buttonLabel = "Request private-beta access",
  microCopy = "Free during beta · Limited spots · We reply within a few days",
  onSuccess,
  onAttempt,
  onError,
}: Props) {
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [status, setStatus] = useState<Status>("idle");
  const [errorMsg, setErrorMsg] = useState("");
  const emailId = useId();
  const consentId = useId();

  const submitDisabled = !consent || status === "submitting";

  async function onSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (submitDisabled) return;
    setErrorMsg("");

    if (!EMAIL_RE.test(email.trim())) {
      setErrorMsg("Please enter a valid email address.");
      return;
    }

    setStatus("submitting");
    onAttempt?.();

    try {
      await requestBetaAccess({ email, source, consented: consent });
      setStatus("success");
      onSuccess?.(email);
    } catch (err) {
      const errStatus = isApiError(err) ? err.status : null;
      const message = isApiError(err) ? err.message : "";
      if (errStatus === 409) {
        setErrorMsg(
          message ||
            "This email is already in our private-beta queue. Hang tight — we'll be in touch.",
        );
      } else if (errStatus === 422) {
        setErrorMsg("Please check your email and try again.");
      } else if (errStatus === 429) {
        setErrorMsg("Too many requests. Please try again in an hour.");
      } else {
        setErrorMsg("Something went wrong. Please try again.");
      }
      setStatus("error");
      onError?.(errStatus);
    }
  }

  if (status === "success") {
    return (
      <div
        role="status"
        aria-live="polite"
        className="rounded-xl bg-brand-primary-soft px-5 py-4 font-sans text-base text-ink-primary"
      >
        Thanks — you're on the list. We'll email an invite within a few days.
      </div>
    );
  }

  return (
    <form
      onSubmit={onSubmit}
      noValidate
      className="flex w-full flex-col gap-3"
      aria-describedby={errorMsg ? `${emailId}-err` : undefined}
    >
      <div className="flex flex-col gap-2 md:flex-row">
        <label htmlFor={emailId} className="sr-only">
          Email
        </label>
        <input
          id={emailId}
          type="email"
          required
          autoComplete="email"
          placeholder="your@email.com"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="flex-1 rounded-xl bg-white px-4 py-3 font-sans text-base text-ink-primary ring-1 ring-border-subtle focus:outline-none focus:ring-2 focus:ring-brand-primary"
        />
        <button
          type="submit"
          aria-disabled={submitDisabled}
          className={`rounded-xl px-5 py-3 font-sans text-base font-medium transition-colors ${
            submitDisabled
              ? "cursor-not-allowed bg-brand-primary-soft text-ink-muted"
              : "bg-brand-primary text-ink-primary hover:shadow-[0_0_0_6px_var(--color-brand-primary-glow)]"
          }`}
        >
          {buttonLabel}
        </button>
      </div>

      <label
        htmlFor={consentId}
        className="flex items-start gap-2 font-sans text-sm text-ink-muted"
      >
        <input
          id={consentId}
          type="checkbox"
          checked={consent}
          onChange={(e) => setConsent(e.target.checked)}
          className="mt-0.5"
        />
        <span>
          I have read the{" "}
          <a href="/beta-terms" className="underline">
            beta terms
          </a>{" "}
          and agree to them.
        </span>
      </label>

      {microCopy && (
        <p className="font-sans text-xs text-ink-muted">{microCopy}</p>
      )}
      {errorMsg && (
        <p
          id={`${emailId}-err`}
          role="alert"
          className="font-sans text-sm text-red-700"
        >
          {errorMsg}
        </p>
      )}
    </form>
  );
}
