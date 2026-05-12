import { type ReactNode, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router";
import { getConsents } from "@/api/consent";

interface Props {
  children: ReactNode;
}

export default function RequireConsent({ children }: Props) {
  const location = useLocation();
  const [hasConsent, setHasConsent] = useState<boolean | null>(null);

  useEffect(() => {
    getConsents()
      .then((consents) => {
        const record = consents.find(
          (c) => c.consent_type === "health_data_processing",
        );
        setHasConsent(record?.granted === true);
      })
      .catch(() => setHasConsent(false));
  }, []);

  if (hasConsent === null) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <div className="text-gray-500">Checking consent...</div>
      </div>
    );
  }

  if (!hasConsent) {
    return (
      <Navigate
        to={`/consent?redirect=${encodeURIComponent(location.pathname)}`}
        replace
      />
    );
  }

  return <>{children}</>;
}
