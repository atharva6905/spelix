import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router";
import { supabase } from "@/lib/supabase";
import { capture } from "@/lib/posthog";
import LandingNav from "@/components/landing/LandingNav";
import LandingHero from "@/components/landing/LandingHero";
import LandingProblem from "@/components/landing/LandingProblem";
import LandingProcess from "@/components/landing/LandingProcess";
import LandingReport from "@/components/landing/LandingReport";
import LandingScience from "@/components/landing/LandingScience";
import LandingPrivacy from "@/components/landing/LandingPrivacy";
import LandingCTA from "@/components/landing/LandingCTA";
import LandingFooter from "@/components/landing/LandingFooter";
import LandingChrome from "@/components/landing/LandingChrome";

export default function LandingPage() {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);
  const finalRef = useRef<HTMLElement>(null);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        void navigate("/upload", { replace: true });
      } else {
        setChecking(false);
        capture("landing_view", {
          referrer: document.referrer || null,
        });
      }
    });
  }, [navigate]);

  if (checking) {
    return (
      <p className="flex min-h-screen items-center justify-center bg-landing-bg text-sm text-landing-text-muted">
        Loading…
      </p>
    );
  }

  return (
    <div className="landing-root">
      <div className="landing-grain" aria-hidden="true" />
      <LandingChrome finalRef={finalRef} />
      <LandingNav />
      <LandingHero />
      <LandingProblem />
      <LandingProcess />
      <LandingReport />
      <LandingScience />
      <LandingPrivacy />
      <LandingCTA ref={finalRef} />
      <LandingFooter />
    </div>
  );
}
