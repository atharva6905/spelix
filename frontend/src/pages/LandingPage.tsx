import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { supabase } from "@/lib/supabase";
import NavBar from "@/components/landing/NavBar";
import Hero from "@/components/landing/Hero";
import ProblemSection from "@/components/landing/ProblemSection";
import HowItWorksSection from "@/components/landing/HowItWorksSection";
import DifferentiatorsSection from "@/components/landing/DifferentiatorsSection";
import PrivacySection from "@/components/landing/PrivacySection";
import FinalCtaSection from "@/components/landing/FinalCtaSection";
import Footer from "@/components/landing/Footer";

export default function LandingPage() {
  const navigate = useNavigate();
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      if (data.session) {
        void navigate("/upload", { replace: true });
      } else {
        setChecking(false);
      }
    });
  }, [navigate]);

  if (checking) {
    return (
      <p className="flex min-h-screen items-center justify-center bg-surface-page text-sm text-ink-muted">
        Loading…
      </p>
    );
  }

  return (
    <main className="bg-surface-page">
      <NavBar />
      <Hero />
      <ProblemSection />
      <HowItWorksSection />
      <DifferentiatorsSection />
      <PrivacySection />
      <FinalCtaSection />
      <Footer />
    </main>
  );
}
