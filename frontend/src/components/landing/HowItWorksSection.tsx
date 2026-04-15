import SectionHeading from "./SectionHeading";
import SectionLabel from "./SectionLabel";
import SectionWrapper from "./SectionWrapper";

const STEPS = [
  {
    n: "01",
    icon: "/landing/step-1-upload.svg",
    title: "Upload your video.",
    body: "Film your squat, bench, or deadlift from the side with your phone. One working set is enough. Spelix accepts standard phone video — no special camera, rig, or studio required.",
  },
  {
    n: "02",
    icon: "/landing/step-2-analyse.svg",
    title: "Spelix analyses every rep.",
    body: "Computer vision tracks 33 body landmarks per frame across your entire lift. Each rep is measured individually: joint angles at key phases, bar path, eccentric tempo, bilateral balance, and sticking-point location. You will see things about your lift that have never been quantified for you before.",
  },
  {
    n: "03",
    icon: "/landing/step-3-coach.svg",
    title: "You get coaching that cites its sources.",
    body: "Results include a streaming written coaching breakdown across four dimensions — Movement Quality, Technique, Path & Balance, and Control — with each claim grounded in peer-reviewed exercise science. Hover on any coaching sentence to see the study it is drawn from: title, authors, year, link.",
  },
] as const;

const GETS = [
  "Per-rep biomechanical scores (so fatigue patterns across your set are visible)",
  "Annotated video with skeleton overlay showing what the computer vision detected",
  "Downloadable PDF report with full session analysis",
  "Follow-up chat — ask the system anything about your analysis",
];

export default function HowItWorksSection() {
  return (
    <SectionWrapper id="how-it-works" variant="dark">
      <SectionLabel variant="dark">How it works</SectionLabel>
      <SectionHeading variant="dark">Three steps, one lift at a time.</SectionHeading>

      <div className="mt-12 grid gap-6 md:grid-cols-3">
        {STEPS.map((s) => (
          <article
            key={s.n}
            className="flex flex-col justify-between rounded-[40px] bg-surface-dark p-8 ring-1 ring-white/10"
          >
            <div>
              <div className="flex items-center justify-between">
                <span className="font-display text-lg text-ink-on-dark-muted">
                  {s.n}
                </span>
                <img
                  src={s.icon}
                  alt=""
                  className="h-10 w-10"
                  loading="lazy"
                />
              </div>
              <h3 className="mt-8 font-display text-xl font-normal tracking-[-0.02em] text-ink-on-dark">
                {s.title}
              </h3>
              <p className="mt-4 font-sans text-base text-ink-on-dark-muted">
                {s.body}
              </p>
            </div>
          </article>
        ))}
      </div>

      <ul className="mt-12 grid gap-3 font-sans text-base text-ink-on-dark-muted md:grid-cols-2">
        {GETS.map((g) => (
          <li key={g} className="flex items-start gap-3">
            <span aria-hidden="true" className="mt-2 h-1.5 w-1.5 rounded-full bg-brand-primary" />
            <span>{g}</span>
          </li>
        ))}
      </ul>
    </SectionWrapper>
  );
}
