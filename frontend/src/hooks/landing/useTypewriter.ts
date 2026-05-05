import { useEffect, useRef, useState } from "react";

export function useTypewriter(text: string, wordDelay = 40) {
  const ref = useRef<HTMLDivElement>(null);
  const [displayText, setDisplayText] = useState("");
  const [isDone, setIsDone] = useState(false);
  const started = useRef(false);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
      setDisplayText(text);
      setIsDone(true);
      return;
    }

    const io = new IntersectionObserver(
      ([entry]) => {
        if (!entry.isIntersecting || started.current) return;
        started.current = true;
        io.disconnect();

        const tokens = text.split(/(\s+)/);
        let idx = 0;

        const scheduleNext = () => {
          if (idx >= tokens.length) {
            setIsDone(true);
            return;
          }

          const token = tokens[idx];
          idx++;

          setDisplayText((prev) => prev + token);

          const isWhitespace = /^\s+$/.test(token);
          setTimeout(scheduleNext, isWhitespace ? 0 : wordDelay);
        };

        setTimeout(scheduleNext, 380);
      },
      { threshold: 0.25 },
    );

    io.observe(el);
    return () => io.disconnect();
  }, [text, wordDelay]);

  return { ref, displayText, isDone };
}
