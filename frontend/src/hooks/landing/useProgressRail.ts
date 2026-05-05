import { useCallback, useEffect, useRef, useState } from "react";

interface SectionPosition {
  id: string;
  topPercent: number;
}

export function useProgressRail() {
  const [fillPercent, setFillPercent] = useState(0);
  const [sections, setSections] = useState<SectionPosition[]>([]);
  const [activeSection, setActiveSection] = useState<string | null>(null);
  const ioRef = useRef<IntersectionObserver | null>(null);

  const placeDots = useCallback(() => {
    const docH = document.documentElement.scrollHeight;
    const els = document.querySelectorAll<HTMLElement>("[data-section]");
    const positions: SectionPosition[] = [];

    els.forEach((el) => {
      const id = el.dataset.section!;
      const topPercent = (el.offsetTop / docH) * 100;
      positions.push({ id, topPercent });
    });

    setSections(positions);
  }, []);

  useEffect(() => {
    placeDots();
    window.addEventListener("resize", placeDots);
    return () => window.removeEventListener("resize", placeDots);
  }, [placeDots]);

  useEffect(() => {
    const onScroll = () => {
      const scrollH = document.documentElement.scrollHeight - window.innerHeight;
      const pct = scrollH > 0 ? (window.scrollY / scrollH) * 100 : 0;
      setFillPercent(pct);
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    const els = document.querySelectorAll<HTMLElement>("[data-section]");
    if (!els.length) return;

    ioRef.current = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveSection(
              (entry.target as HTMLElement).dataset.section ?? null,
            );
          }
        }
      },
      { threshold: 0.3 },
    );

    els.forEach((el) => ioRef.current!.observe(el));
    return () => ioRef.current?.disconnect();
  }, []);

  return { fillPercent, sections, activeSection };
}
