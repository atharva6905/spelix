import { type RefObject, useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "spelix_sticky_dismissed";

export function useStickyBar(finalRef: RefObject<HTMLElement | null>) {
  const [dismissed, setDismissed] = useState(() => {
    try {
      return sessionStorage.getItem(STORAGE_KEY) === "1";
    } catch {
      return false;
    }
  });
  const [isVisible, setIsVisible] = useState(false);

  const dismiss = useCallback(() => {
    setDismissed(true);
    setIsVisible(false);
    try {
      sessionStorage.setItem(STORAGE_KEY, "1");
    } catch {
      /* sessionStorage unavailable */
    }
  }, []);

  useEffect(() => {
    if (dismissed) return;

    const onScroll = () => {
      const past = window.scrollY > window.innerHeight;
      const finalEl = finalRef.current;
      let finalVisible = false;

      if (finalEl) {
        const rect = finalEl.getBoundingClientRect();
        finalVisible = rect.top < window.innerHeight - 80;
      }

      setIsVisible(past && !finalVisible);
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, [dismissed, finalRef]);

  return { isVisible, dismiss };
}
