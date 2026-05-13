"use strict";
// generate_expert_guide.cjs
// Generates Spelix_Expert_Reviewer_Guide.docx using the docx npm package (v9.x)
// Run: node generate_expert_guide.cjs

const fs = require("fs");
const path = require("path");

const {
  Document,
  Packer,
  Paragraph,
  TextRun,
  Table,
  TableRow,
  TableCell,
  Header,
  Footer,
  AlignmentType,
  LevelFormat,
  HeadingLevel,
  BorderStyle,
  WidthType,
  ShadingType,
  VerticalAlign,
  PageNumber,
  PageBreak,
} = require("./node_modules/docx");

// ─────────────────────────────────────────────
//  CONSTANTS
// ─────────────────────────────────────────────
const CONTENT_W = 9360; // DXA — US Letter minus 1" margins each side
const DARK_BLUE = "1F3864";
const MID_BLUE = "2E75B6";
const LIGHT_BLUE_BG = "D5E8F0";
const HEADER_BG = "2E75B6";
const HEADER_FG = "FFFFFF";
const TABLE_GRAY = "F2F2F2";
const FONT = "Arial";

// Numbering reference counter — every distinct list gets its own reference
let _numRef = 0;
function nextRef() {
  _numRef += 1;
  return `list-${_numRef}`;
}

// ─────────────────────────────────────────────
//  HELPERS
// ─────────────────────────────────────────────

/** Standard single-line border config for tables */
const stdBorder = { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC" };
const stdBorders = {
  top: stdBorder,
  bottom: stdBorder,
  left: stdBorder,
  right: stdBorder,
  insideH: stdBorder,
  insideV: stdBorder,
};

/** Cell with optional header shading */
function makeCell(children, widthDxa, { isHeader = false, shade = null, vAlign = VerticalAlign.TOP } = {}) {
  const shadingCfg = isHeader
    ? { fill: HEADER_BG, type: ShadingType.CLEAR }
    : shade
    ? { fill: shade, type: ShadingType.CLEAR }
    : { fill: "FFFFFF", type: ShadingType.CLEAR };
  return new TableCell({
    borders: stdBorders,
    width: { size: widthDxa, type: WidthType.DXA },
    shading: shadingCfg,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: vAlign,
    children,
  });
}

/** Paragraph containing a plain TextRun */
function p(text, opts = {}) {
  const {
    bold = false,
    italic = false,
    color = undefined,
    size = 22, // 11 pt
    spacing = {},
    align = AlignmentType.LEFT,
    heading = undefined,
    pageBreakBefore = false,
  } = opts;
  const run = new TextRun({ text, bold, italic, color, size, font: FONT });
  return new Paragraph({
    heading,
    alignment: align,
    pageBreakBefore,
    spacing: { before: 80, after: 80, ...spacing },
    children: [run],
  });
}

/** A blank spacer paragraph */
function spacer(before = 80) {
  return new Paragraph({ spacing: { before, after: 0 }, children: [new TextRun("")] });
}

/** Section heading at H1 level */
function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, size: 32, font: FONT, color: DARK_BLUE })],
  });
}

/** Sub-section heading at H2 level */
function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 200, after: 100 },
    children: [new TextRun({ text, bold: true, size: 26, font: FONT, color: MID_BLUE })],
  });
}

/** Sub-sub heading H3 */
function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 160, after: 80 },
    children: [new TextRun({ text, bold: true, size: 24, font: FONT, color: "333333" })],
  });
}

/** Bold label + normal text on same line */
function labeledPara(label, text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    children: [
      new TextRun({ text: label + ": ", bold: true, size: 22, font: FONT }),
      new TextRun({ text, size: 22, font: FONT }),
    ],
  });
}

/** A bullet paragraph using a given numbering reference */
function bullet(text, ref, { bold = false, italic = false, size = 22 } = {}) {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, bold, italic, size, font: FONT })],
  });
}

/** A numbered paragraph */
function numbered(text, ref, { bold = false, italic = false, size = 22 } = {}) {
  return new Paragraph({
    numbering: { reference: ref, level: 0 },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, bold, italic, size, font: FONT })],
  });
}

/** 2-column table: [[cell1text, cell2text], ...], colWidths must sum to CONTENT_W */
function twoColTable(rows, colWidths, headerRow = null) {
  const [w1, w2] = colWidths;
  const tableRows = [];
  if (headerRow) {
    tableRows.push(
      new TableRow({
        tableHeader: true,
        children: [
          makeCell([p(headerRow[0], { bold: true, color: HEADER_FG, size: 22 })], w1, { isHeader: true }),
          makeCell([p(headerRow[1], { bold: true, color: HEADER_FG, size: 22 })], w2, { isHeader: true }),
        ],
      })
    );
  }
  rows.forEach(([c1, c2], i) => {
    const shade = i % 2 === 0 ? "FFFFFF" : TABLE_GRAY;
    tableRows.push(
      new TableRow({
        children: [
          makeCell([p(c1, { size: 22 })], w1, { shade }),
          makeCell([p(c2, { size: 22 })], w2, { shade }),
        ],
      })
    );
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: tableRows,
  });
}

/** 3-column table helper */
function threeColTable(rows, colWidths, headerRow = null) {
  const [w1, w2, w3] = colWidths;
  const tableRows = [];
  if (headerRow) {
    tableRows.push(
      new TableRow({
        tableHeader: true,
        children: [
          makeCell([p(headerRow[0], { bold: true, color: HEADER_FG })], w1, { isHeader: true }),
          makeCell([p(headerRow[1], { bold: true, color: HEADER_FG })], w2, { isHeader: true }),
          makeCell([p(headerRow[2], { bold: true, color: HEADER_FG })], w3, { isHeader: true }),
        ],
      })
    );
  }
  rows.forEach(([c1, c2, c3], i) => {
    const shade = i % 2 === 0 ? "FFFFFF" : TABLE_GRAY;
    tableRows.push(
      new TableRow({
        children: [
          makeCell([p(c1, { size: 22 })], w1, { shade }),
          makeCell([p(c2, { size: 22 })], w2, { shade }),
          makeCell([p(c3, { size: 22 })], w3, { shade }),
        ],
      })
    );
  });
  return new Table({
    width: { size: CONTENT_W, type: WidthType.DXA },
    columnWidths: colWidths,
    rows: tableRows,
  });
}

/** Page-break paragraph */
function pgBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

// ─────────────────────────────────────────────
//  NUMBERING CONFIG (one entry per list used)
// ─────────────────────────────────────────────
// We pre-declare all references we'll use so Document sees them.

const REF = {
  welcome_bullets: nextRef(),
  exercises_bullets: nextRef(),
  login_steps: nextRef(),
  portal_layout: nextRef(),
  queue_priority: nextRef(),
  review_steps: nextRef(),
  annotation_fields: nextRef(),
  annotation_squat: nextRef(),
  annotation_bench: nextRef(),
  annotation_deadlift: nextRef(),
  golden_criteria: nextRef(),
  paper_steps: nextRef(),
  paper_what: nextRef(),
  paper_journals: nextRef(),
  threshold_steps: nextRef(),
  language_bullets: nextRef(),
  coach_brain_bullets: nextRef(),
  privacy_bullets: nextRef(),
  faq_bullets: nextRef(),
  walkthrough_steps: nextRef(),
  walkthrough_bullets: nextRef(),
};

function makeNumberingConfig() {
  const bulletLevel = (ref) => ({
    reference: ref,
    levels: [
      {
        level: 0,
        format: LevelFormat.BULLET,
        text: "•",
        alignment: AlignmentType.LEFT,
        style: {
          paragraph: { indent: { left: 720, hanging: 360 } },
          run: { font: FONT },
        },
      },
    ],
  });
  const numberLevel = (ref) => ({
    reference: ref,
    levels: [
      {
        level: 0,
        format: LevelFormat.DECIMAL,
        text: "%1.",
        alignment: AlignmentType.LEFT,
        style: {
          paragraph: { indent: { left: 720, hanging: 360 } },
          run: { font: FONT },
        },
      },
    ],
  });

  return {
    config: [
      bulletLevel(REF.welcome_bullets),
      bulletLevel(REF.exercises_bullets),
      numberLevel(REF.login_steps),
      bulletLevel(REF.portal_layout),
      numberLevel(REF.queue_priority),
      numberLevel(REF.review_steps),
      numberLevel(REF.annotation_fields),
      bulletLevel(REF.annotation_squat),
      bulletLevel(REF.annotation_bench),
      bulletLevel(REF.annotation_deadlift),
      bulletLevel(REF.golden_criteria),
      numberLevel(REF.paper_steps),
      bulletLevel(REF.paper_what),
      bulletLevel(REF.paper_journals),
      numberLevel(REF.threshold_steps),
      bulletLevel(REF.language_bullets),
      bulletLevel(REF.coach_brain_bullets),
      bulletLevel(REF.privacy_bullets),
      numberLevel(REF.faq_bullets),
      numberLevel(REF.walkthrough_steps),
      bulletLevel(REF.walkthrough_bullets),
    ],
  };
}

// ─────────────────────────────────────────────
//  HEADER / FOOTER
// ─────────────────────────────────────────────

function makeHeader() {
  return new Header({
    children: [
      new Paragraph({
        alignment: AlignmentType.RIGHT,
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: MID_BLUE, space: 4 } },
        spacing: { before: 0, after: 80 },
        children: [
          new TextRun({ text: "SPELIX  |  Expert Reviewer Guide  |  v2.1", size: 18, font: FONT, color: MID_BLUE, bold: true }),
        ],
      }),
    ],
  });
}

function makeFooter() {
  return new Footer({
    children: [
      new Paragraph({
        alignment: AlignmentType.CENTER,
        border: { top: { style: BorderStyle.SINGLE, size: 6, color: MID_BLUE, space: 4 } },
        spacing: { before: 80, after: 0 },
        children: [
          new TextRun({ text: "Confidential — For authorised reviewers only     Page ", size: 18, font: FONT, color: "555555" }),
          new TextRun({ children: [PageNumber.CURRENT], size: 18, font: FONT, color: MID_BLUE, bold: true }),
          new TextRun({ text: " of ", size: 18, font: FONT, color: "555555" }),
          new TextRun({ children: [PageNumber.TOTAL_PAGES], size: 18, font: FONT, color: MID_BLUE, bold: true }),
        ],
      }),
    ],
  });
}

// ─────────────────────────────────────────────
//  TITLE PAGE
// ─────────────────────────────────────────────
function buildTitlePage() {
  return [
    spacer(2400),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 160 },
      children: [new TextRun({ text: "SPELIX", bold: true, size: 72, font: FONT, color: DARK_BLUE })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 120 },
      children: [new TextRun({ text: "Expert Reviewer Guide", bold: true, size: 48, font: FONT, color: MID_BLUE })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 120 },
      children: [new TextRun({ text: "Science-Based Barbell Form Coaching", italic: true, size: 28, font: FONT, color: "444444" })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 0, after: 200 },
      children: [new TextRun({ text: "Version 2.1  |  May 2026", size: 24, font: FONT, color: "555555" })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { before: 200, after: 0 },
      children: [
        new TextRun({
          text: "Confidential — For authorised reviewers only. Do not distribute.",
          italic: true,
          size: 20,
          font: FONT,
          color: "888888",
        }),
      ],
    }),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  GLOSSARY
// ─────────────────────────────────────────────
function buildGlossary() {
  const terms = [
    ["CV pipeline", "The computer vision system that analyses your uploaded video. It tracks body joints frame-by-frame to measure angles, timing, and bar path."],
    ["RAG corpus", "The knowledge base of research papers that the AI draws from when generating coaching. RAG stands for Retrieval-Augmented Generation — the AI looks up relevant papers before writing its advice."],
    ["Coach Brain", "A growing library of validated coaching insights. Think of it as the AI's memory of what works — built from expert-reviewed analyses over time."],
    ["CoVe (Chain-of-Verification)", "An automated fact-checking step where the AI verifies its own coaching claims against the research papers before presenting them to the user."],
    ["Distillation", "The process of extracting the most useful coaching insights from a completed analysis and adding them to the Coach Brain."],
    ["Qdrant", "The database that stores the research paper knowledge base. You don't interact with it directly — it powers the citation system behind the scenes."],
    ["Pose landmark", "A specific body point (e.g. hip, knee, ankle, shoulder) that the CV pipeline tracks in the video. Landmark visibility determines the confidence level."],
    ["Golden dataset", "A curated set of exemplary analyses where the AI coaching was accurate and complete. Used to benchmark AI quality over time."],
    ["Ingestion", "The process of extracting text from a PDF paper, splitting it into chunks, and adding those chunks to the knowledge base so the AI can cite them."],
    ["Threshold", "A numeric cutoff used by the CV pipeline to score movements (e.g. depth angle ≤90° = parallel). You can propose changes to these values."],
  ];

  return [
    h1("Glossary"),
    p("The following terms appear throughout this guide. Read this page before continuing.", { spacing: { before: 80, after: 120 } }),
    twoColTable(terms, [2880, 6480], ["Term", "What It Means"]),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 1 — WELCOME & OVERVIEW
// ─────────────────────────────────────────────
function buildSection1() {
  const exRows = [
    ["Squat", "High Bar, Low Bar"],
    ["Bench Press", "Flat, Incline, Decline"],
    ["Deadlift", "Conventional, Sumo, Romanian"],
  ];

  const bRef = REF.welcome_bullets;

  return [
    h1("1.  Welcome & Overview"),
    p(
      "Welcome to Spelix. Spelix is a science-based barbell coaching platform: users upload short " +
        "squat, bench press, or deadlift videos and receive structured, citation-grounded coaching " +
        "generated by an AI pipeline. Your role as Expert Reviewer is to evaluate that coaching for " +
        "accuracy, completeness, and alignment with the peer-reviewed literature.",
      { spacing: { before: 80, after: 100 } }
    ),
    p(
      "AI coaching validated by a Kinesiology specialist (B.Sc. candidate). All coaching claims are " +
        "grounded in peer-reviewed literature reviewed and curated by a qualified expert.",
      { italic: true, color: MID_BLUE, spacing: { before: 60, after: 100 } }
    ),

    h2("Your responsibilities include:"),
    bullet("Scoring AI-generated coaching for quality and accuracy.", bRef),
    bullet("Flagging incorrect, misleading, or unsupported coaching claims.", bRef),
    bullet("Uploading relevant peer-reviewed papers to expand the knowledge base.", bRef),
    bullet("Proposing threshold adjustments backed by literature.", bRef),
    bullet("Labelling exemplary analyses as golden dataset entries.", bRef),

    spacer(120),
    labeledPara("Time commitment", "Approximately 2–3 hours per week, fully asynchronous. There are no scheduled meetings."),
    spacer(80),

    h2("Supported Exercises"),
    twoColTable(exRows, [3120, 6240], ["Exercise", "Variants"]),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 2 — GETTING STARTED
// ─────────────────────────────────────────────
function buildSection2() {
  const loginRows = [
    ["URL", "https://spelix.app/login"],
    ["Email", "expert@spelix.app"],
    ["Password", "Provided separately via secure channel"],
  ];
  const navRows = [
    ["Upload", "Upload a video for analysis"],
    ["History", "View your past uploaded analyses"],
    ["Profile", "Manage account settings"],
    ["Expert Portal", "Your annotation and paper management workspace"],
  ];
  const tabRows = [
    ["Flagged", "Analyses that users or the system have flagged for urgent review"],
    ["Low Quality", "Analyses with a Confidence score below the Low threshold"],
    ["First Run", "Analyses that have never been reviewed by an expert"],
    ["My Papers", "Research papers you have uploaded, with ingestion status"],
  ];

  return [
    h1("2.  Getting Started"),

    h2("Login"),
    twoColTable(loginRows, [2160, 7200]),
    spacer(100),
    p("Important: change your password immediately after your first login. Go to Profile > Change Password.", {
      bold: true,
      color: "CC0000",
      spacing: { before: 80, after: 80 },
    }),

    spacer(120),
    h2("Navigation Bar"),
    p("After logging in you will see the following items in the top navigation bar:", { spacing: { before: 60, after: 80 } }),
    twoColTable(navRows, [2160, 7200], ["Nav Item", "Purpose"]),

    spacer(120),
    h2("Expert Portal"),
    p(
      "Click Expert Portal in the navigation bar to reach your main workspace. This area is visible " +
        "only to you and platform administrators.",
      { spacing: { before: 60, after: 80 } }
    ),

    h2("Consent Gate"),
    p(
      "The consent gate does not block Expert Portal routes. Every analysis that appears in your " +
        "queue comes from a user who explicitly consented to health data processing under GDPR " +
        "Article 9 and to human expert review. You do not need to obtain or verify consent yourself.",
      { spacing: { before: 60, after: 80 } }
    ),

    h2("Expert Portal Layout"),
    p("The portal header contains two action buttons:", { spacing: { before: 60, after: 60 } }),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [
        new TextRun({ text: "Upload Paper", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — add a new research PDF to the knowledge base.", size: 22, font: FONT }),
      ],
    }),
    new Paragraph({
      spacing: { before: 40, after: 80 },
      children: [
        new TextRun({ text: "Validate Thresholds", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — review and flag movement scoring thresholds.", size: 22, font: FONT }),
      ],
    }),
    p("Below the buttons, a tab bar gives access to four views:", { spacing: { before: 60, after: 80 } }),
    twoColTable(tabRows, [2880, 6480], ["Tab", "Contents"]),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 3 — THE REVIEW QUEUE
// ─────────────────────────────────────────────
function buildSection3() {
  const colRows = [
    ["Analysis ID", "Truncated identifier shown in grey monospace."],
    ["Exercise", "The exercise type: Squat, Bench Press, or Deadlift."],
    ["Variant", "The specific variant (e.g. High Bar, Conventional)."],
    ["Confidence", "Colour-coded badge: High (green), Moderate (blue), Low (yellow), Very Low (red)."],
    ["Flagged", "Orange badge if flagged; a dash otherwise."],
    ["Annotations", "How many annotations have been submitted for this analysis."],
    ["Created", "Date the analysis was created (UTC)."],
    ["Action", "Review button — opens the analysis detail page."],
  ];
  const prRef = REF.queue_priority;

  return [
    h1("3.  The Review Queue"),
    p(
      "The Flagged, Low Quality, and First Run tabs each display analyses that need your evaluation. " +
        "The queue shows 20 items per page with Previous / Next pagination. When a tab is empty you " +
        "will see: No analyses in this queue.",
      { spacing: { before: 80, after: 100 } }
    ),

    h2("Queue Table Columns"),
    twoColTable(colRows, [2880, 6480], ["Column", "Description"]),

    spacer(120),
    h2("Priority Order"),
    p("Work through the tabs in this order:", { spacing: { before: 60, after: 60 } }),
    numbered("Flagged — highest priority. The system or an administrator has flagged a concern.", prRef),
    numbered("Low Quality — the CV pipeline had low confidence in its pose data.", prRef),
    numbered("First Run — the analysis has never had a human review.", prRef),

    spacer(120),
    h2("Auto-Failed Analyses"),
    p(
      "A nightly cleanup job runs at 03:30 UTC and automatically marks any analysis that has been " +
        "stuck in a non-terminal state for more than 2 hours as failed. When you open the detail page, " +
        "you will see an error message starting with \"Auto-failed:\". These analyses produce no coaching output. " +
        "Skip them unless they are also flagged.",
      { spacing: { before: 60, after: 100 } }
    ),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 4 — REVIEWING AN ANALYSIS
// ─────────────────────────────────────────────
function buildSection4() {
  const scoreRows = [
    ["Overall", "Weighted composite of the four dimensions below (see Section 9 for weights and detail)."],
    ["Movement Quality", "Excessive torso lean, acute knee angles, shoulder/elbow range violations. Score < 3.0 triggers a red alert."],
    ["Technique", "Squat depth vs parallel, hip hinge depth, elbow angle range, rep-to-rep depth consistency."],
    ["Path & Balance", "Bar path consistency across reps and front-to-back deviation from midfoot. Defaults to 5.0 if bar path data unavailable."],
    ["Control", "Descent tempo (penalises drops < 1.0–1.5 s) and lockout completeness (hip+knee or elbow ≥ 165°)."],
  ];
  const scoreDescRows = [
    ["9.0 – 10.0", "Elite", "Green"],
    ["7.5 – 8.9", "Advanced", "Green"],
    ["5.0 – 7.4", "Intermediate", "Amber"],
    ["3.0 – 4.9", "Needs Work", "Red"],
    ["0.0 – 2.9", "Needs Attention", "Red"],
  ];
  const annotationRef = REF.annotation_fields;
  const sqRef = REF.annotation_squat;
  const bnRef = REF.annotation_bench;
  const dlRef = REF.annotation_deadlift;

  return [
    h1("4.  Reviewing an Analysis"),
    p(
      "Click the Review button on any queue row to open the analysis detail page. A breadcrumb at the " +
        "top reads ← Back to Expert Portal — use it to return to the queue without losing your place.",
      { spacing: { before: 80, after: 100 } }
    ),

    h2("4.1  Analysis Metrics"),
    p(
      "The Analysis Metrics card appears at the top of the detail page. Its header displays the " +
        "exercise name, variant, confidence badge, flagged badge (if applicable), golden badge (if " +
        "applicable), and total rep count detected by the CV pipeline.",
      { spacing: { before: 60, after: 80 } }
    ),

    h3("Score Dimensions"),
    p("Five score cards are displayed in a grid:", { spacing: { before: 60, after: 60 } }),
    twoColTable(scoreRows, [2880, 6480], ["Score Card", "What it measures"]),

    spacer(100),
    h3("Score Colour and Descriptors"),
    threeColTable(scoreDescRows, [2160, 3600, 3600], ["Range", "Descriptor", "Card Colour"]),

    spacer(100),
    p(
      "If the Movement Quality score is below 3.0, a red alert banner appears below the score grid. " +
        "Pay particular attention to the coaching in this case.",
      { bold: true, color: "CC0000", spacing: { before: 60, after: 100 } }
    ),

    h3("Annotated Video"),
    p(
      "Below the score grid, if an annotated video was produced by the pipeline, an embedded video " +
        "player displays a skeleton overlay with joint angle labels and a rep counter. Use it to " +
        "verify whether the AI coaching matches what actually happened in the lift.",
      { spacing: { before: 60, after: 60 } }
    ),
    p(
      "Note: raw user video is never shown. You will only ever see the anonymised skeleton overlay. " +
        "No identifiable features of the user are visible.",
      { italic: true, color: "555555", spacing: { before: 40, after: 80 } }
    ),

    h3("Eval Scores"),
    p(
      "Below the video player, colour-coded evaluation cards show three signals from the automated " +
        "quality pipeline:",
      { spacing: { before: 60, after: 60 } }
    ),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [
        new TextRun({ text: "Faithfulness", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — the percentage of coaching claims that are directly supported by the cited papers. Green if ≥80 %, red if below.", size: 22, font: FONT }),
      ],
    }),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [
        new TextRun({ text: "Fact-Check / CoVe", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — whether the Chain-of-Verification step confirmed all claims. Displays Verified or Not verified.", size: 22, font: FONT }),
      ],
    }),
    new Paragraph({
      spacing: { before: 40, after: 80 },
      children: [
        new TextRun({ text: "Unsupported Claims", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — each claim that the CoVe step could not verify is listed individually.", size: 22, font: FONT }),
      ],
    }),

    h2("4.2  Coaching Output"),
    p(
      "The Coaching Output card follows the metrics card. It is structured into the following " +
        "sub-sections:",
      { spacing: { before: 60, after: 60 } }
    ),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text: "Summary — ", bold: true, size: 22, font: FONT }), new TextRun({ text: "One-paragraph overview of the lift.", size: 22, font: FONT })],
    }),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text: "Movement Quality Alerts — ", bold: true, size: 22, font: FONT }), new TextRun({ text: "Highlighted in a red card. Review these first.", size: 22, font: FONT })],
    }),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text: "Strengths — ", bold: true, size: 22, font: FONT }), new TextRun({ text: "Positive observations.", size: 22, font: FONT })],
    }),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text: "Issues — ", bold: true, size: 22, font: FONT }), new TextRun({ text: "Each issue carries a severity badge (High / Medium / Low).", size: 22, font: FONT })],
    }),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [new TextRun({ text: "Recommended Cues — ", bold: true, size: 22, font: FONT }), new TextRun({ text: "Actionable coaching cues.", size: 22, font: FONT })],
    }),
    new Paragraph({
      spacing: { before: 40, after: 80 },
      children: [new TextRun({ text: "Citations — ", bold: true, size: 22, font: FONT }), new TextRun({ text: "Numbered list showing Author, Year, Title, and DOI. Hover the [1], [2] superscripts in the coaching text to see paper details in a tooltip.", size: 22, font: FONT })],
    }),
    p("If the pipeline produced no coaching, the card displays: No coaching output available for this analysis.", {
      italic: true,
      color: "888888",
      spacing: { before: 40, after: 80 },
    }),

    // ── 4.3 Common AI Failure Patterns ──
    h2("4.3  Common AI Failure Patterns"),
    p(
      "The AI coaching is generally accurate, but it has known blind spots. " +
        "Watch for these specific patterns when reviewing:",
      { spacing: { before: 60, after: 60 } }
    ),

    threeColTable(
      [
        [
          "Knee valgus hallucination",
          "The AI claims knee valgus (inward collapse), knee varus, elbow flare, grip width, or stance width. None of these are measurable from the side-view camera.",
          "Flag as false positive using \"AI identified a non-issue\". This is the most common AI error.",
        ],
        [
          "Generic coaching cues",
          "Vague advice like \"maintain good form\" or \"keep your core tight\" without specifying which rep, which joint, or what to change.",
          "Lower the Coaching Quality Score. Note in Suggested Corrections that cues should reference specific reps and joints.",
        ],
        [
          "Missing inline citation markers",
          "Citations listed at the bottom but no [1], [2] markers in the coaching text. Markers must appear inline where claims are made.",
          "Flag as a quality issue. Citations without inline markers don't help the user trace claims to evidence.",
        ],
        [
          "Unsupported claims (red faithfulness)",
          "Faithfulness eval score is red (below 80%). Some coaching claims are not backed by cited papers. Coaching is NOT suppressed — user sees it as-is.",
          "Check each coaching claim against the cited papers. Flag specific unsupported claims using issue checkboxes and free-text fields.",
        ],
        [
          "Severity misordering",
          "A Medium or Low severity issue appears before a High severity issue. High-severity issues should be listed first.",
          "Note in Suggested Corrections that issues should be reordered by severity.",
        ],
        [
          "Prohibited language",
          "Terms like \"injury risk\", \"injury prevention\", \"diagnose\", \"treatment\", or \"clinical\" in the coaching text.",
          "Flag using \"AI identified a non-issue\" and note the prohibited term. See Section 8.",
        ],
        [
          "Overclaiming depth issues",
          "AI flags depth as insufficient when score cards show depth angle at or below 90° (parallel).",
          "Cross-reference depth angle in rep metrics against the coaching claim. If numbers contradict, flag it.",
        ],
      ],
      [2200, 3800, 3360],
      ["Pattern", "What To Look For", "What To Do"]
    ),

    new Paragraph({ children: [new PageBreak()] }),

    // ── 4.4 What Good vs Bad Coaching Looks Like ──
    h2("4.4  What Good vs Bad Coaching Looks Like"),
    p(
      "Use these examples to calibrate your quality judgments. A Coaching Quality Score of 8+ " +
        "should match the \"good\" column; a score below 5 should match the \"bad\" column.",
      { spacing: { before: 60, after: 60 } }
    ),

    threeColTable(
      [
        [
          "Specificity",
          "\"On rep 3, your hip angle reached 95°. Drive your hips back further to break 90°.\"",
          "\"Try to go deeper on your squats.\"",
        ],
        [
          "Citation use",
          "\"Maintaining torso angle below 45° reduces lumbar shear force [1]. Your torso reached 52° on rep 2.\"",
          "\"Your form could be better.\" (No citations, no rep reference.)",
        ],
        [
          "Safety warnings",
          "\"Movement Quality alert: Torso lean exceeded 50° on reps 2 and 4. Consider reducing load.\"",
          "\"You might get injured if you keep lifting like this.\" (Prohibited language.)",
        ],
        [
          "Cues",
          "\"Cue: spread the floor apart with your feet during descent. This engages hip external rotators.\"",
          "\"Keep your knees out.\" (Too vague, no mechanism.)",
        ],
        [
          "Issue severity",
          "High: \"Excessive forward lean (52° on rep 2) [2].\" Medium: \"Tempo inconsistency — rep 4 was 0.8s vs 1.2s avg.\"",
          "All issues marked Medium. No rep numbers or measurements.",
        ],
      ],
      [1400, 4200, 3760],
      ["Aspect", "Good Coaching (score 8+)", "Bad Coaching (score < 5)"]
    ),

    // ── 4.5 Annotation Walkthrough ──
    h2("4.5  Annotation Walkthrough — Worked Example"),
    p(
      "Here is a step-by-step walkthrough of how to review a squat analysis. Use this as a " +
        "mental model for your first few reviews.",
      { spacing: { before: 60, after: 60 } }
    ),

    p("Scenario: A high-bar squat analysis with 5 reps, Moderate confidence, Movement Quality score of 5.8.", {
      bold: true,
      spacing: { before: 40, after: 40 },
    }),

    numbered("Open the analysis detail page. Note the confidence badge is blue (Moderate) — scores are generally reliable but double-check any borderline claims.", REF.walkthrough_steps),
    numbered("Check the 5 score cards. Movement Quality is 5.8 (Intermediate, amber). Technique is 7.2, Path & Balance is 8.1, Control is 6.0.", REF.walkthrough_steps),
    numbered("Watch the annotated video. Look for excessive torso lean (Movement Quality) and inconsistent reps (Control). Note what you observe.", REF.walkthrough_steps),
    numbered("Read the coaching output. The AI says: \"Depth was adequate on all reps, with hip angles ranging from 82° to 88°.\" Cross-check against the rep metrics.", REF.walkthrough_steps),
    numbered("The AI also says: \"Knee valgus was observed on rep 3.\" Knee valgus cannot be measured from side view. This is a false positive.", REF.walkthrough_steps),
    numbered("Check citations. Hover [1] and [2] markers — are the cited papers relevant? Do markers appear inline, or only at the bottom?", REF.walkthrough_steps),
    numbered("Check eval scores. Faithfulness 91% (green). CoVe Verified. No unsupported claims. Good sign.", REF.walkthrough_steps),
    numbered("Fill in the annotation form:", REF.walkthrough_steps),
    bullet("Coaching Quality Score: 6.5 (decent overall, but the valgus false positive brings it down)", REF.walkthrough_bullets),
    bullet("Movement Quality Advice Accurate: Yes (torso lean observation matches the video)", REF.walkthrough_bullets),
    bullet("Engagement Advice Accurate: Yes (cues are specific and actionable)", REF.walkthrough_bullets),
    bullet("Issue: check \"Knee tracking issues at depth\", set severity Medium, note: \"AI claimed knee valgus from side view — not measurable. False positive.\"", REF.walkthrough_bullets),
    bullet("AI identified a non-issue: \"Knee valgus on rep 3 — not visible from sagittal camera angle.\"", REF.walkthrough_bullets),
    bullet("Do NOT mark as golden — the false positive disqualifies it.", REF.walkthrough_bullets),
    numbered("Click Submit. Green banner confirms success.", REF.walkthrough_steps),

    new Paragraph({ children: [new PageBreak()] }),

    // ── 4.6 Previous Annotations (renumbered from 4.3) ──
    h2("4.6  Previous Annotations"),
    p(
      "If you have previously submitted an annotation for this analysis, it appears in a " +
        "'Previous Annotations' section above your form. Each past annotation shows the quality " +
        "score, accuracy ratings, and any corrections you submitted. This lets you see your prior assessments.",
      { spacing: { before: 60, after: 80 } }
    ),

    h2("4.7  Your Annotation Form"),
    p("Complete all relevant fields and click Submit.", { spacing: { before: 60, after: 80 } }),

    numbered("Coaching Quality Score — Enter a value from 1.0 to 10.0 in increments of 0.1. This is your overall judgment of the coaching output quality.", annotationRef),
    numbered("Movement Quality Advice Accurate? — Radio buttons: Yes / No / N/A. Select N/A if there are no Movement Quality alerts in the output.", annotationRef),
    numbered("Engagement Advice Accurate? — Radio buttons: Yes / No / N/A. Select N/A if the coaching contains no engagement-related advice.", annotationRef),
    numbered("Issues Identified — Tick the issues present in the lift. Checkboxes are grouped by exercise and each has a severity (High / Medium / Low) and an optional notes field that appears when you tick it.", annotationRef),

    spacer(80),
    p("Squat issues:", { bold: true, spacing: { before: 80, after: 40 } }),
    bullet("Insufficient depth", sqRef),
    bullet("Excessive forward lean", sqRef),
    bullet("Knee tracking issues at depth", sqRef),
    bullet("Incomplete lockout", sqRef),
    bullet("Inconsistent rep tempo", sqRef),

    spacer(80),
    p("Bench Press issues:", { bold: true, spacing: { before: 80, after: 40 } }),
    bullet("Excessive shoulder angle at bottom", bnRef),
    bullet("Incomplete lockout", bnRef),
    bullet("Inconsistent rep tempo", bnRef),
    bullet("Bar path deviation", bnRef),

    spacer(80),
    p("Deadlift issues:", { bold: true, spacing: { before: 80, after: 40 } }),
    bullet("Excessive torso lean at start", dlRef),
    bullet("Incomplete hip extension at lockout", dlRef),
    bullet("Inconsistent rep tempo", dlRef),
    bullet("Bar path deviation", dlRef),

    spacer(80),
    p("Additional free-text fields:", { bold: true, spacing: { before: 80, after: 40 } }),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [
        new TextRun({ text: "AI missed an issue", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — describe an issue the AI coaching did not mention.", size: 22, font: FONT }),
      ],
    }),
    new Paragraph({
      spacing: { before: 40, after: 80 },
      children: [
        new TextRun({ text: "AI identified a non-issue", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — describe something the AI flagged that is not actually a problem.", size: 22, font: FONT }),
      ],
    }),

    numbered("Suggested Corrections — Free-text area. Describe any corrections the AI should have made to its coaching.", annotationRef),
    numbered("Cited Sources — Add specific papers that support your assessment. Each entry has fields for Title, Authors, Year, and DOI. Click + Add Source to add a row. Click Remove to delete one.", annotationRef),
    numbered("Mark as golden dataset entry — Tick this if the analysis and coaching meet all golden quality criteria (see Section 5). Golden entries are used for fine-tuning and evaluation benchmarks.", annotationRef),

    spacer(100),
    p(
      "Click Submit. The button changes to Submitting… while the request is in flight. On success a " +
        "green banner reads: Annotation submitted successfully. If the score is out of range or a " +
        "network error occurs, a red error message appears below the form.",
      { spacing: { before: 60, after: 100 } }
    ),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 5 — GOLDEN DATASET
// ─────────────────────────────────────────────
function buildSection5() {
  const gcRef = REF.golden_criteria;
  return [
    h1("5.  Golden Dataset Labelling"),
    p(
      "A golden dataset entry is an analysis where the AI coaching was so accurate and complete that " +
        "it can serve as a benchmark for evaluating future AI outputs. Use this label sparingly.",
      { spacing: { before: 80, after: 100 } }
    ),

    h2("Criteria for a Golden Entry"),
    p("All of the following must be true:", { spacing: { before: 60, after: 60 } }),
    bullet("The coaching accurately describes the lift as shown in the annotated video.", gcRef),
    bullet("All significant issues are identified with correct severity.", gcRef),
    bullet("No false positives — the AI has not flagged anything that is not actually a problem.", gcRef),
    bullet("Citations are relevant, correctly attributed, and support the coaching claims.", gcRef),
    bullet("Any Movement Quality alerts are appropriate and correctly worded (see Section 8 for language rules).", gcRef),

    spacer(120),
    h2("Targets"),
    p(
      "Aim for approximately 10 % of reviewed analyses to be marked golden. Keep the golden set " +
        "balanced across exercises and variants to avoid benchmark bias.",
      { spacing: { before: 60, after: 100 } }
    ),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 6 — UPLOADING PAPERS
// ─────────────────────────────────────────────
function buildSection6() {
  const formRows = [
    ["Title", "Required. Full paper title."],
    ["Authors", "Comma-separated list of author surnames and initials."],
    ["Year", "Four-digit publication year."],
    ["DOI", "Digital Object Identifier without the https://doi.org/ prefix."],
    ["Exercise Tags", "Checkboxes: Squat, Bench Press, Deadlift. Select all that apply."],
    ["Quality Tier", "Select from the four tiers (see table below)."],
    ["Study Design", "Select from the six designs (see table below)."],
    ["PDF File", "Required. Max 50 MB. Must be a text-extractable PDF (not a scanned image)."],
  ];
  const tierRows = [
    ["L1", "Systematic Review", "Highest evidence weight. Meta-analyses and systematic reviews."],
    ["L2", "RCT", "Randomised controlled trials."],
    ["L3", "Observational", "Cohort, cross-sectional, and case-control studies."],
    ["L4", "Guideline", "Expert consensus statements and clinical practice guidelines."],
  ];
  const designRows = [
    ["RCT", "Randomised controlled trial"],
    ["Observational", "Cohort or cross-sectional study"],
    ["Systematic Review", "Systematic review or meta-analysis"],
    ["Narrative Review", "Narrative or scoping review"],
    ["Guideline", "Clinical or expert consensus guideline"],
    ["Other", "Any design not listed above"],
  ];
  const dashCols = [
    ["Title", "Paper title (truncated if long)"],
    ["Authors", "Comma-separated author list (may be truncated for long lists)."],
    ["Tags", "Exercise tag chips"],
    ["Tier", "Quality tier badge"],
    ["Status", "Current ingestion status"],
    ["Chunks", "Number of text chunks in the knowledge base (0 until approved)"],
    ["Uploaded", "Upload date (UTC)"],
    ["Action", "Approve & Ingest button (visible only for pending papers)"],
  ];
  const statusRows = [
    ["Pending", "Yellow", "Awaiting your approval. Chunks = 0."],
    ["Approved", "Green", "Approved and queued for ingestion. Chunks update once processing completes (1–2 min)."],
    ["Rejected", "Red", "Rejected by an administrator."],
    ["Needs Revision", "Orange", "An administrator has requested changes before the paper can be approved."],
  ];
  const stepRef = REF.paper_steps;
  const whatRef = REF.paper_what;
  const journalRef = REF.paper_journals;

  return [
    h1("6.  Uploading Research Papers"),
    p(
      "Expanding the knowledge base is one of your most impactful contributions. The AI can only " +
        "cite papers that have been ingested. Upload papers you trust, from high-quality journals.",
      { spacing: { before: 80, after: 100 } }
    ),

    h2("Step-by-Step Upload Process"),
    numbered("Click Upload Paper in the Expert Portal header.", stepRef),
    numbered("Fill in the metadata form (see fields table below). Title and PDF File are required.", stepRef),
    numbered("Select your PDF file (max 50 MB).", stepRef),
    numbered("Click the Upload Paper button. The button label changes through three stages: \"Requesting upload URL...\" → \"Uploading...\" (with a progress bar and percentage) → \"Finalizing...\". Wait for it to complete.", stepRef),
    numbered("A green success banner confirms the upload.", stepRef),
    numbered("The My Papers tab now shows the paper with status Pending.", stepRef),
    numbered("Click Approve & Ingest to start ingestion.", stepRef),
    numbered("Wait 1–2 minutes, then refresh. The Chunks column should show a positive number.", stepRef),

    spacer(120),
    h2("Upload Form Fields"),
    twoColTable(formRows, [2880, 6480], ["Field", "Description"]),

    spacer(120),
    h2("Quality Tiers"),
    threeColTable(tierRows, [720, 2160, 6480], ["Code", "Label", "Description"]),

    spacer(120),
    h2("Study Designs"),
    twoColTable(designRows, [2880, 6480], ["Design", "Meaning"]),

    spacer(120),
    h2("My Papers Dashboard"),
    p("The My Papers tab shows all papers you have uploaded:", { spacing: { before: 60, after: 80 } }),
    twoColTable(dashCols, [2160, 7200], ["Column", "Contents"]),

    spacer(120),
    h2("Paper Statuses"),
    threeColTable(statusRows, [2160, 1800, 5400], ["Status", "Badge Colour", "Meaning"]),

    spacer(120),
    h2("What Papers to Upload"),
    p("Recommended journals:", { bold: true, spacing: { before: 80, after: 60 } }),
    bullet("Journal of Strength and Conditioning Research", journalRef),
    bullet("International Journal of Sports Physiology and Performance", journalRef),
    bullet("Sports Biomechanics", journalRef),
    bullet("European Journal of Sport Science", journalRef),
    bullet("Journal of Biomechanics", journalRef),
    bullet("Medicine & Science in Sports & Exercise", journalRef),

    spacer(100),
    p("Priority topics:", { bold: true, spacing: { before: 80, after: 60 } }),
    bullet("Squat depth, knee tracking, and bar path biomechanics", whatRef),
    bullet("Bench press shoulder position and pec activation", whatRef),
    bullet("Deadlift lumbar flexion and hip hinge mechanics", whatRef),
    bullet("Tempo and rate of force development", whatRef),
    bullet("Powerlifting technique guidelines and rule books", whatRef),

    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 7 — THRESHOLD VALIDATION
// ─────────────────────────────────────────────
function buildSection7() {
  const thRef = REF.threshold_steps;
  return [
    h1("7.  Threshold Validation"),
    p(
      "Thresholds are the numeric cutoffs the CV pipeline uses to score each movement. For example, " +
        "the squat depth threshold says that a hip angle ≤90° counts as reaching parallel. If you " +
        "believe a threshold is wrong based on the literature, you can flag it.",
      { spacing: { before: 80, after: 100 } }
    ),

    h2("Access"),
    p(
      "Click the Validate Thresholds button in the Expert Portal header. This opens a separate page " +
        "(not a tab). It has two sub-tabs:",
      { spacing: { before: 60, after: 60 } }
    ),
    new Paragraph({
      spacing: { before: 40, after: 40 },
      children: [
        new TextRun({ text: "Current Thresholds", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — a read-only table of all active thresholds. Each row has a Flag button.", size: 22, font: FONT }),
      ],
    }),
    new Paragraph({
      spacing: { before: 40, after: 80 },
      children: [
        new TextRun({ text: "My Flags", bold: true, size: 22, font: FONT }),
        new TextRun({ text: " — the flags you have submitted, with their review status.", size: 22, font: FONT }),
      ],
    }),

    h2("How to Flag a Threshold"),
    numbered("On the Current Thresholds sub-tab, find the threshold you want to challenge.", thRef),
    numbered("Click the Flag button on that row.", thRef),
    numbered("A modal opens with three fields: Proposed Value, Citation (minimum 5 characters), and Rationale (minimum 20 characters).", thRef),
    numbered("Fill in all fields. The citation should be a DOI or a short author-year reference.", thRef),
    numbered("Click Submit.", thRef),

    spacer(100),
    p(
      "Changes to thresholds are applied by Atharva via a code review (PR). You propose; Atharva " +
        "applies after verifying the literature. You will see the status of your flag update in the " +
        "My Flags sub-tab.",
      { spacing: { before: 60, after: 100 } }
    ),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 8 — LANGUAGE RULES
// ─────────────────────────────────────────────
function buildSection8() {
  const langRows = [
    ["Injury risk", "Movement quality concern", "Spelix is not a medical device and does not diagnose injury risk."],
    ["Injury prevention", "Movement quality improvement", "Same reason as above."],
    ["Safety score", "Movement Quality Score", "The official name of the metric is Movement Quality Score."],
    ["Diagnose", "Observe", "Reviewers and the AI make observations, not diagnoses."],
    ["Treatment", "Coaching recommendation", "This is educational feedback, not medical treatment."],
    ["Medical advice", "Educational feedback", "The platform provides coaching, not medical advice."],
  ];

  return [
    h1("8.  Language Rules"),
    p(
      "Spelix is a coaching tool, not a medical device. Certain words are prohibited in all " +
        "user-facing content, including your annotation text. These rules are enforced by automated " +
        "checks but you should apply them yourself first.",
      { spacing: { before: 80, after: 100 } }
    ),
    threeColTable(langRows, [2160, 2880, 4320], ["Never Say", "Instead Say", "Reason"]),
    spacer(120),
    p("These rules apply to everything you write: annotation notes, suggested corrections, flag rationales, and uploaded paper descriptions.", {
      italic: true,
      color: "555555",
      spacing: { before: 60, after: 100 },
    }),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 9 — SCORING SYSTEM
// ─────────────────────────────────────────────
function buildSection9() {
  const dimRows = [
    ["Movement Quality (40%)", "Penalises threshold violations that indicate potentially harmful mechanics: excessive torso lean (squat/deadlift), acute knee angle at depth (squat), excessive shoulder opening (bench), elbow/shoulder range violations (bench). Capped at 5.0 when confidence is Very Low. Score < 3.0 triggers a red alert banner."],
    ["Technique (30%)", "Evaluates execution against the target variant: squat depth relative to parallel, hip hinge depth (deadlift), elbow angle range at bottom (bench), plus rep-to-rep depth consistency across all exercises (std dev > 10° triggers a penalty)."],
    ["Path & Balance (20%)", "Bar path consistency (how repeatable the bar trajectory is across reps) and anterior-posterior deviation (how far the bar drifts from the midfoot line). Returns a default 5.0 when bar path data is unavailable."],
    ["Control (10%)", "Eccentric (descent) tempo — penalises drops faster than 1.0 s or 1.5 s — plus lockout completeness at the top of each rep (hip+knee ≥ 165° for squat/deadlift, elbow ≥ 165° for bench)."],
    ["Overall", "Weighted composite of the four dimensions above. Weights shown in parentheses."],
  ];
  const descRows = [
    ["9.0 – 10.0", "Elite", "Green card"],
    ["7.5 – 8.9", "Advanced", "Green card"],
    ["5.0 – 7.4", "Intermediate", "Amber card"],
    ["3.0 – 4.9", "Needs Work", "Red card"],
    ["0.0 – 2.9", "Needs Attention", "Red card"],
  ];
  const measRows = [
    ["Hip angle at depth", "YES", "Tracked by BlazePose landmark pairs."],
    ["Knee angle at depth", "YES", "Tracked by BlazePose landmark pairs."],
    ["Bar path deviation", "YES", "Derived from wrist landmark trajectory."],
    ["Rep tempo", "YES", "Measured from landmark velocity over time."],
    ["Grip width", "NO", "Not measurable from a side-view camera."],
    ["Stance width", "NO", "Not measurable from a side-view camera."],
    ["Knee valgus / varus", "NO", "Requires a frontal-view camera. If the AI mentions knee valgus, flag it as a false positive."],
    ["Scapular retraction", "NO", "Not visible from a side-view camera."],
  ];

  return [
    h1("9.  Understanding the Scoring System"),
    p("Spelix scores each analysis on five dimensions.", { spacing: { before: 80, after: 100 } }),

    h2("Score Dimensions"),
    twoColTable(dimRows, [2880, 6480], ["Dimension", "What it measures"]),

    spacer(120),
    h2("Score Descriptors"),
    threeColTable(descRows, [2160, 3600, 3600], ["Range", "Descriptor", "Card Display"]),

    spacer(100),
    p(
      "If the Movement Quality score is below 3.0, a red warning banner appears on the analysis " +
        "detail page. This indicates the CV pipeline detected a high-concern movement pattern.",
      { bold: true, color: "CC0000", spacing: { before: 60, after: 100 } }
    ),

    h2("Camera-Measurable vs Non-Measurable Dimensions"),
    p(
      "The AI can only coach on what the camera can see. If the coaching output refers to a " +
        "dimension that is not camera-measurable, flag it as a false positive in your annotation " +
        "using the AI identified a non-issue free-text field.",
      { spacing: { before: 60, after: 80 } }
    ),
    threeColTable(measRows, [3600, 1440, 4320], ["Dimension", "Measurable?", "Notes"]),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 10 — CONFIDENCE LEVELS
// ─────────────────────────────────────────────
function buildSection10() {
  const confRows = [
    ["High", "Green", "≥80 %", "Strong pose data. All key landmarks visible. Coaching is reliable."],
    ["Moderate", "Blue", "65 – 79 %", "Most landmarks visible. Minor occlusions. Coaching is generally reliable."],
    ["Low", "Yellow", "50 – 64 %", "Some landmarks occluded. The AI may have made inferences. Scrutinise carefully."],
    ["Very Low", "Red", "<50 %", "Significant pose uncertainty. Coaching may contain errors. Flag issues you spot."],
  ];

  return [
    h1("10.  Confidence Levels"),
    p(
      "Confidence reflects how well the CV pipeline could track the lifter's pose throughout the " +
        "video. It is an aggregate of landmark visibility scores across all key joints.",
      { spacing: { before: 80, after: 100 } }
    ),
    new Table({
      width: { size: CONTENT_W, type: WidthType.DXA },
      columnWidths: [1440, 1440, 1440, 5040],
      rows: [
        new TableRow({
          tableHeader: true,
          children: [
            makeCell([p("Level", { bold: true, color: HEADER_FG })], 1440, { isHeader: true }),
            makeCell([p("Badge Colour", { bold: true, color: HEADER_FG })], 1440, { isHeader: true }),
            makeCell([p("Score Range", { bold: true, color: HEADER_FG })], 1440, { isHeader: true }),
            makeCell([p("Meaning", { bold: true, color: HEADER_FG })], 5040, { isHeader: true }),
          ],
        }),
        ...confRows.map(([lvl, clr, range, meaning], i) => {
          const shade = i % 2 === 0 ? "FFFFFF" : TABLE_GRAY;
          return new TableRow({
            children: [
              makeCell([p(lvl, { bold: true })], 1440, { shade }),
              makeCell([p(clr)], 1440, { shade }),
              makeCell([p(range)], 1440, { shade }),
              makeCell([p(meaning)], 5040, { shade }),
            ],
          });
        }),
      ],
    }),
    spacer(120),
    p(
      "When reviewing Low or Very Low confidence analyses, pay extra attention to whether the " +
        "coaching makes claims that appear inconsistent with what you can see in the annotated video. " +
        "The AI may have filled gaps with assumptions.",
      { spacing: { before: 60, after: 100 } }
    ),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 11 — COACH BRAIN
// ─────────────────────────────────────────────
function buildSection11() {
  const cbRef = REF.coach_brain_bullets;
  return [
    h1("11.  Coach Brain & How Your Work Compounds"),
    p(
      "Coach Brain is the AI's growing memory of validated coaching insights. Every annotation you " +
        "submit has the potential to improve future coaching for every user.",
      { spacing: { before: 80, after: 100 } }
    ),

    h2("How Your Work Feeds Coach Brain"),
    p("Two processes feed Coach Brain — one automated, one driven by your annotations:", { spacing: { before: 60, after: 60 } }),
    bullet("An automated pipeline extracts candidate coaching insights from every completed analysis that passes a quality threshold. These candidates are reviewed by an administrator before entering Coach Brain.", cbRef),
    bullet("Your annotations inform which candidates are approved or rejected. When you flag issues or correct coaching, the administrator uses your feedback to decide what enters the knowledge base.", cbRef),
    bullet("When you mark an analysis as a golden entry, it enters a benchmark dataset used to measure AI quality over time.", cbRef),

    spacer(120),
    p(
      "Your work compounds: a correction you submit today may improve the coaching generated for " +
        "hundreds of analyses in the future. The platform grows more accurate with every expert review.",
      { italic: true, color: MID_BLUE, spacing: { before: 60, after: 100 } }
    ),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 12 — PRIVACY
// ─────────────────────────────────────────────
function buildSection12() {
  const prRef = REF.privacy_bullets;
  return [
    h1("12.  Privacy & Data Handling"),
    p(
      "Spelix collects biometric movement data (video-derived pose landmarks), which is special " +
        "category data under GDPR Article 9. The platform has a completed Data Protection Impact " +
        "Assessment (DPIA) covering all data flows.",
      { spacing: { before: 80, after: 100 } }
    ),

    h2("What Users Consent To"),
    bullet("Processing of health-related movement data for coaching purposes.", prRef),
    bullet("Human expert review of their analysis by a qualified Kinesiology specialist.", prRef),
    bullet("Storage of their analysis metrics for up to 24 months.", prRef),

    spacer(100),
    h2("What You Will and Will Not See"),
    bullet("You will NEVER see raw user video. Only the anonymised skeleton overlay is available to you.", prRef),
    bullet("You will see analysis metrics, coaching text, score cards, eval scores, and the skeleton overlay.", prRef),
    bullet("Annotated video files and uploaded PDFs are retained for 7 days. Analysis metrics are retained for 24 months.", prRef),

    spacer(100),
    h2("Consent Withdrawal"),
    p(
      "If a user withdraws their consent, a background process removes their data from the Coach Brain " +
        "and their analyses may be removed from the review queue. You may notice analyses disappearing " +
        "from the queue — this is expected behaviour.",
      { spacing: { before: 60, after: 80 } }
    ),

    h2("Your Obligations"),
    bullet("Do not download, screenshot, or share any user data, coaching output, or annotated video.", prRef),
    bullet("Do not attempt to re-identify any user from the skeleton overlay or analysis metadata.", prRef),
    bullet("Report any suspected data breach immediately to atharva6905@gmail.com.", prRef),

    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 13 — TROUBLESHOOTING
// ─────────────────────────────────────────────
function buildSection13() {
  const rows = [
    ["Queue fails to load (spinning indefinitely)", "Hard-refresh the page (Ctrl+Shift+R / Cmd+Shift+R). If it persists, log out and back in. Report to Atharva if the problem continues."],
    ["Annotation submission fails with a red error", "Check that your Coaching Quality Score is between 1.0 and 10.0. Verify your internet connection. Try submitting again. If the error persists, copy the error text and email Atharva."],
    ["Paper upload fails at the progress bar", "Ensure the PDF is text-extractable (not a scanned image), is under 50 MB, and your internet connection is stable. Try again. If it still fails, note the file name and report it."],
    ["Approve & Ingest button fails", "Refresh the My Papers tab. If the status is still Pending, try clicking the button again after 30 seconds. Report to Atharva if it continues to fail."],
    ["Chunks column stays at 0 after 2 minutes", "Wait one more minute, then refresh. If chunks remain at 0 after 3 minutes total, the ingestion pipeline may have encountered a parsing error. Report the paper title to Atharva."],
    ["Access denied when navigating to Expert Portal", "Your account may not have the expert role assigned. Email Atharva with the email address you used to log in."],
    ["Page shows a permission-checking spinner that never resolves", "Clear browser cookies for spelix.app, log out, and log back in. If this does not fix it, try a different browser."],
    ["Threshold flag modal won't submit", "Ensure Citation is at least 5 characters and Rationale is at least 20 characters. Both fields are required. Check that Proposed Value is a valid number."],
  ];

  return [
    h1("13.  Troubleshooting"),
    p("Use the table below to resolve common issues before contacting Atharva.", { spacing: { before: 80, after: 100 } }),
    twoColTable(rows, [3600, 5760], ["Problem", "What To Do"]),
    pgBreak(),
  ];
}

// ─────────────────────────────────────────────
//  SECTION 14 — FAQ
// ─────────────────────────────────────────────
function buildSection14() {
  const faqs = [
    [
      "Can I upload my own training videos for analysis?",
      "Yes, but you need to go through the standard user consent flow first. Navigate to the Upload page, upload your video, and grant consent when prompted. Your analyses will then appear in History. They will not appear in the Expert Portal review queue.",
    ],
    [
      "The AI has given advice that I believe is incorrect. What should I do?",
      "Flag the issue in your annotation. Set the relevant issue checkbox to severity High, describe the problem in the AI identified a non-issue or AI missed an issue free-text fields, and lower your Coaching Quality Score accordingly. This flags the analysis for administrator attention.",
    ],
    [
      "How do my annotations actually affect the AI coaching?",
      "Your annotations feed a distillation pipeline that extracts validated coaching insights and adds them to Coach Brain. Coach Brain is consulted during future coaching generation. High-quality annotations with correct issues and citations have the most impact.",
    ],
    [
      "My uploaded paper shows chunk_count = 0. Is something broken?",
      "Not necessarily. Click Approve & Ingest on the My Papers tab, then wait 1–2 minutes and refresh. Ingestion is asynchronous. If chunks are still 0 after 3 minutes, report the paper title to Atharva.",
    ],
    [
      "I see an analysis marked Auto-failed. What happened?",
      "A nightly cleanup job at 03:30 UTC marks analyses that have been processing for more than 2 hours as failed. These analyses have no coaching output. You can skip them unless they are also flagged.",
    ],
    [
      "How do I flag a threshold I believe is set incorrectly?",
      "Click Validate Thresholds in the Expert Portal header. On the Current Thresholds sub-tab, find the threshold and click Flag. Fill in the proposed value, a citation, and a rationale of at least 20 characters, then click Submit.",
    ],
    [
      "Can I see the user's raw video?",
      "No. Raw user video is never surfaced in the Expert Portal. You can see the annotated skeleton video on the analysis detail page — it shows a wireframe overlay of the lifter's joints with angle labels and a rep counter, but no identifiable features of the user are visible.",
    ],
    [
      "Who do I contact for help?",
      "Email Atharva Kulkarni at atharva6905@gmail.com. Include your reviewer email address, a description of the problem, and any error messages you see.",
    ],
  ];

  const children = [
    h1("14.  Frequently Asked Questions"),
    spacer(80),
  ];

  faqs.forEach(([q, a], i) => {
    children.push(
      new Paragraph({
        spacing: { before: 120, after: 40 },
        children: [new TextRun({ text: `Q${i + 1}: ${q}`, bold: true, size: 22, font: FONT, color: MID_BLUE })],
      })
    );
    children.push(p(a, { spacing: { before: 40, after: 80 } }));
  });

  children.push(pgBreak());
  return children;
}

// ─────────────────────────────────────────────
//  APPENDIX A — KEY ANGLE THRESHOLDS
// ─────────────────────────────────────────────
function buildAppendixA() {
  const squatRows = [
    ["Hip angle at depth", "≤90°", "Hip must reach parallel (thigh parallel to floor) or below."],
    ["Hip/knee at standing lockout", "≥160°", "Full extension at the top of each rep."],
    ["Torso forward lean", ">45° from vertical", "Triggers excessive forward lean flag."],
    ["Knee angle at depth", "<70°", "Deep squat indicator."],
    ["Hip + knee at lockout", "≥165° combined", "Incomplete lockout flag threshold."],
  ];
  const benchRows = [
    ["Elbow angle at bar touch", "<90°", "Elbow must break 90° at the bottom."],
    ["Elbow at lockout", "≥160°", "Full extension required at top."],
    ["Shoulder angle at bottom", ">75° abduction", "Triggers excessive shoulder angle flag."],
    ["Elbow full lockout", "≥165°", "Incomplete lockout threshold."],
  ];
  const dlRows = [
    ["Hip angle at setup (conventional)", "<70°", "Triggers excessive torso lean flag for conventional."],
    ["Hip angle at setup (RDL)", "<90°", "Triggers excessive torso lean flag for Romanian."],
    ["Hip/knee at standing lockout", "≥160°", "Full hip extension required."],
    ["Torso angle at setup", ">50° from vertical", "Triggers excessive torso lean flag."],
    ["Hip lockout", "≥165° AND shoulders behind bar", "Both conditions required for complete lockout."],
  ];
  const genRows = [
    ["Minimum rep duration", "≥0.5 s", "Shorter movements are classified as partial reps."],
    ["Angle hysteresis", "±5°", "Dead-band applied to all thresholds to prevent oscillation."],
    ["High confidence", "≥80 %", "All key landmarks consistently visible."],
    ["Moderate confidence", "65–79 %", "Most landmarks visible; minor occlusions tolerated."],
    ["Low confidence", "50–64 %", "Some landmarks occluded; inferences made."],
    ["Very Low confidence", "<50 %", "Significant pose uncertainty."],
  ];

  return [
    h1("Appendix A:  Key Angle Thresholds"),
    p(
      "The values below are the defaults shipped with Spelix v2.1. They may be updated following " +
        "expert flag review. Always check the Validate Thresholds page for the live values.",
      { italic: true, spacing: { before: 80, after: 120 } }
    ),

    h2("Squat Thresholds"),
    threeColTable(squatRows, [3240, 1800, 4320], ["Measurement", "Threshold", "Notes"]),

    spacer(120),
    h2("Bench Press Thresholds"),
    threeColTable(benchRows, [3240, 1800, 4320], ["Measurement", "Threshold", "Notes"]),

    spacer(120),
    h2("Deadlift Thresholds"),
    threeColTable(dlRows, [3240, 1800, 4320], ["Measurement", "Threshold", "Notes"]),

    spacer(120),
    h2("General Parameters"),
    threeColTable(genRows, [3240, 1800, 4320], ["Parameter", "Value", "Notes"]),

    spacer(120),
    p("Note: all angle measurements use the anatomical convention (full extension = 180°) unless otherwise stated.", {
      italic: true,
      color: "888888",
      spacing: { before: 60, after: 60 },
    }),
  ];
}

// ─────────────────────────────────────────────
//  DOCUMENT ASSEMBLY
// ─────────────────────────────────────────────

const allChildren = [
  ...buildTitlePage(),
  ...buildGlossary(),
  ...buildSection1(),
  ...buildSection2(),
  ...buildSection3(),
  ...buildSection4(),
  ...buildSection5(),
  ...buildSection6(),
  ...buildSection7(),
  ...buildSection8(),
  ...buildSection9(),
  ...buildSection10(),
  ...buildSection11(),
  ...buildSection12(),
  ...buildSection13(),
  ...buildSection14(),
  ...buildAppendixA(),
];

const doc = new Document({
  numbering: makeNumberingConfig(),

  styles: {
    default: {
      document: {
        run: { font: FONT, size: 22 },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 32, bold: true, font: FONT, color: DARK_BLUE },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 26, bold: true, font: FONT, color: MID_BLUE },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, font: FONT, color: "333333" },
        paragraph: { spacing: { before: 160, after: 80 }, outlineLevel: 2 },
      },
    ],
  },

  sections: [
    {
      properties: {
        page: {
          size: { width: 12240, height: 15840 },
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      headers: { default: makeHeader() },
      footers: { default: makeFooter() },
      children: allChildren,
    },
  ],
});

// ─────────────────────────────────────────────
//  WRITE OUTPUT
// ─────────────────────────────────────────────
const outPath = path.join(__dirname, "Spelix_Expert_Reviewer_Guide.docx");

Packer.toBuffer(doc)
  .then((buffer) => {
    fs.writeFileSync(outPath, buffer);
    const kb = (buffer.length / 1024).toFixed(1);
    console.log(`✓  Written: ${outPath}`);
    console.log(`   Size: ${buffer.length} bytes (${kb} KB)`);
  })
  .catch((err) => {
    console.error("ERROR generating document:", err);
    process.exit(1);
  });
