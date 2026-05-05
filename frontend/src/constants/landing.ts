export const NAV = {
  wordmark: "Spelix",
  badge: "Private Beta",
} as const;

export const HERO = {
  overline: "— Spelix · Barbell Form Coaching —",
  h1Lines: ["Every rep,", "analyzed.", "Every claim, cited."] as const,
  subtitle:
    "Upload a set. Spelix tracks every rep with computer vision, retrieves relevant biomechanics research, and writes your coaching report with inline citations — reviewed by a kinesiology specialist.",
  meta: "Squat · Bench · Deadlift · Peer-reviewed research · Invite only",
  countPrefix: "⬡",
  countText: "47 people on the waitlist",
} as const;

export const PROBLEM_CARDS = [
  {
    tag: "INCONSISTENT",
    tagColor: "rgba(255,107,107,0.7)",
    title: "Same clip. Different feedback.",
    body: "Submit the same clip twice. Get different results. Apps in this space have been caught producing inconsistent scores on identical videos. Advice that changes on resubmission isn't advice — it's noise.",
  },
  {
    tag: "UNVERIFIABLE",
    tagColor: undefined,
    title: "You get feedback. You don't get why.",
    body: "Most AI coaching is plausible-sounding text generated from a model that has never read a kinesiology paper. It might be right. It might not be. There is no way to check.",
  },
  {
    tag: "UNVALIDATED",
    tagColor: undefined,
    title: "No expert in the loop.",
    body: "Generic AI cannot distinguish a coaching cue backed by a randomized controlled trial from a forum post. Spelix's research corpus is reviewed and curated by a kinesiology specialist before any paper enters the system.",
  },
] as const;

export const PROCESS_STEPS = [
  {
    num: "01",
    title: "Upload your lift",
    body: "60 seconds. Front or side view. Full body in frame throughout — Spelix needs to see your feet for deadlift depth and your knees for squat tracking. No calibration required.",
  },
  {
    num: "02",
    title: "Every rep, measured",
    body: "BlazePose tracks 33 landmarks per frame. Reps detected automatically. Four biomechanical metrics computed per lift phase — with a 5-tier confidence score per rep.",
  },
  {
    num: "03",
    title: "Science-backed coaching",
    body: "The system searches a curated biomechanics corpus for research relevant to what it found in your lift. Every coaching claim is checked against retrieved sources before it reaches you. The report includes citations you can look up.",
  },
] as const;

export const DIMENSION_CARDS = [
  {
    index: "Dimension 01",
    name: "Movement Quality",
    description:
      "Movement patterns scored for efficiency and technique breakdown. Calibrated to your declared experience level and body stats — a beginner's squat depth target differs from an advanced lifter's.",
    sparks: [
      { h: "60%", opacity: 0.85 },
      { h: "78%", opacity: 0.95 },
      { h: "90%", opacity: 1 },
      { h: "32%", opacity: 0.35 },
      { h: "82%", opacity: 0.95 },
      { h: "70%", opacity: 0.8 },
      { h: "88%", opacity: 1 },
    ],
  },
  {
    index: "Dimension 02",
    name: "Technique",
    description:
      "Joint angles, bar-body distance, and positional mechanics against published norms for your variant — conventional, sumo, flat, incline, and more.",
    sparks: [
      { h: "72%", opacity: 0.9 },
      { h: "80%", opacity: 1 },
      { h: "55%", opacity: 0.7 },
      { h: "28%", opacity: 0.3 },
      { h: "65%", opacity: 0.8 },
      { h: "90%", opacity: 1 },
    ],
  },
  {
    index: "Dimension 03",
    name: "Path & Balance",
    description:
      "Barbell trajectory mapped against the bar-over-midfoot principle. Lateral drift and vertical path efficiency measured per rep.",
    sparks: [
      { h: "84%", opacity: 0.95 },
      { h: "62%", opacity: 0.75 },
      { h: "92%", opacity: 1 },
      { h: "78%", opacity: 0.9 },
      { h: "35%", opacity: 0.4 },
      { h: "70%", opacity: 0.85 },
    ],
  },
  {
    index: "Dimension 04",
    name: "Control",
    description:
      "Temporal stability across eccentric and concentric phases. Identifies rep-to-rep variance that indicates fatigue or technique breakdown.",
    sparks: [
      { h: "92%", opacity: 1 },
      { h: "88%", opacity: 1 },
      { h: "74%", opacity: 0.85 },
      { h: "58%", opacity: 0.6 },
      { h: "30%", opacity: 0.35 },
      { h: "42%", opacity: 0.5 },
    ],
  },
] as const;

// TODO: replace with real system output before public launch
export const SNIPPET_TEXT =
  '"Hip descent reaches 91° flexion at Rep 3 — within the range associated with effective posterior chain loading for your declared femur length. Bar drift of 11mm lateral at the sticking point is within acceptable bounds for conventional deadlift. Primary correction: maintain neutral cervical spine through lockout — your chin extends noticeably on reps 2 and 4."';

export const SNIPPET_LABEL_INITIAL = "GENERATING...";
export const SNIPPET_LABEL_FINAL =
  "EXAMPLE — CONVENTIONAL DEADLIFT, REP 3";

// TODO: replace with real system output before public launch
export const SNIPPET_CITATIONS = [
  "Escamilla RF et al. (2001) · J Strength Cond Res",
  "Nuckols G · Bar-over-midfoot principle",
  "Comfort P et al. (2020) · J Strength Cond Res",
] as const;

export const STATS = [
  { target: 100, suffix: "%", label: "Of coaching claims cite sources" },
  {
    target: 30,
    suffix: "+",
    label: "Peer-reviewed papers, curated and growing",
  },
  {
    target: 4,
    suffix: "",
    label: "Quality tiers — systematic reviews weighted 2×",
  },
  { target: 3, suffix: "", label: "Lifts — squat, bench press, deadlift" },
] as const;

export const SCIENCE = {
  label: "04 / The Science Layer",
  leadLines: [
    { text: "The coaching isn't generated", italic: false },
    { text: "from thin air.", italic: false },
    { text: "It's retrieved from", italic: true },
    { text: "peer-reviewed literature.", italic: true },
  ] as const,
  bodyPrefix: "The corpus draws from ",
  journals: [
    "Journal of Strength and Conditioning Research",
    "Journal of Biomechanics",
    "Sports Biomechanics",
  ] as const,
  bodySuffix:
    " and two other top kinesiology publications. Papers are evaluated for methodology, recency, and relevance before a specialist reviews and approves them. Coaching that would cite the wrong study doesn't ship.",
  expertQuote:
    '"AI coaching validated by a Kinesiology specialist (B.Sc. candidate). All coaching claims are grounded in peer-reviewed literature reviewed and curated by a qualified expert."',
} as const;

export const PRIVACY_ITEMS = [
  {
    title: "Classified as health data from day one.",
    body: "Your body proportions, movement scores, and session history meet the definition of special-category health data under GDPR Article 9. Explicit opt-in consent is required — separate from Terms of Service.",
  },
  {
    title: "No raw video retained.",
    body: "Uploaded video is converted to anonymous skeleton keypoints immediately after CV processing. The raw video is deleted. What remains is geometry — no identifiable image data.",
  },
  {
    title: "Coaching improves — privately.",
    body: "The system gets smarter from aggregate patterns, not your individual data. Body measurements are stored in categorical ranges. Precise measurements never enter the knowledge layer.",
  },
] as const;

export const CTA = {
  overline: "— Join the Private Beta —",
  headingLine1: "Form coaching",
  headingLine2: "with a ",
  headingEmphasis: "paper trail.",
  subtext:
    "Private beta · Invite only · No credit card · Free during beta",
} as const;

export const FOOTER = {
  copyright: "© 2026 Spelix",
  links: [
    { label: "Privacy Policy", href: "#" },
    { label: "Beta Terms", href: "/beta-terms" },
    { label: "spelix.app", href: "#" },
  ] as const,
  legal:
    "Spelix is not a medical device. Coaching is not medical advice. Movement quality scores are for training guidance only.",
} as const;

export const SECTION_IDS = [
  "hero",
  "problem",
  "process",
  "report",
  "science",
  "privacy",
  "final",
] as const;
