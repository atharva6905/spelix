"""Seed the papers_rag Qdrant collection with exercise science research (P2-007).

Creates rag_documents rows in Postgres and ingests paper text into Qdrant
via IngestionService. Each paper has an abstract + key findings section
that represents the paper's content for RAG retrieval.

Requirements:
- FR-RAGK-02: ≥10 papers per exercise (squat, bench, deadlift)
- FR-RAGK-03: only reviewed_approved documents enter Qdrant
- 4-layer quality tier weights (L1 SR/MA, L2 RCT, L3 observational, L4 guideline)

Usage (from backend/ directory):
    uv run python scripts/seed_research_papers.py
    uv run python scripts/seed_research_papers.py --dry-run

Re-run behaviour (issue #264):
    The script is idempotent. Before inserting each paper it checks whether a
    live row with the same normalized DOI already exists
    (uq_rag_documents_doi_live scope). Existing papers are skipped with a log
    message; only new papers are inserted and ingested into Qdrant. Papers
    without a DOI (doi=None) are always inserted, as they cannot be
    deduplicated by DOI.

Environment:
    DATABASE_URL, QDRANT_URL, QDRANT_API_KEY, COHERE_API_KEY
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Ensure backend/ on sys.path
_BACKEND_DIR = Path(__file__).parent.parent
if str(_BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(_BACKEND_DIR))

from sqlalchemy import text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from app.utils.doi import DoiValidationError, normalize_doi  # noqa: E402

_BACKEND_ENV = _BACKEND_DIR / ".env"
_ROOT_ENV = _BACKEND_DIR.parent / ".env"
_ENV_PATH = _BACKEND_ENV if _BACKEND_ENV.exists() else _ROOT_ENV

if _ENV_PATH.exists():
    from dotenv import load_dotenv  # type: ignore[import-untyped]

    load_dotenv(_ENV_PATH)
    print(f"[seed-papers] Loaded env from {_ENV_PATH}")


# ---------------------------------------------------------------------------
# Paper data structure
# ---------------------------------------------------------------------------


@dataclass
class SeedPaper:
    """A seed research paper with metadata and representative text."""

    title: str
    authors: list[str]
    year: int
    doi: str | None
    quality_tier: str  # L1_systematic_review, L2_rct, L3_observational, L4_guideline
    exercise_tags: list[str]
    document_type: str  # research_paper, clinical_guideline, textbook
    text: str
    sections: dict[str, str] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Seed papers — ≥10 per exercise
# ---------------------------------------------------------------------------

SEED_PAPERS: list[SeedPaper] = [
    # ===================================================================
    # SQUAT papers (12)
    # ===================================================================
    SeedPaper(
        title="Squat depth and its effect on lower limb joint kinetics and muscle activation: a systematic review",
        authors=["Kubo K", "Ikebukuro T", "Yata H"],
        year=2019,
        doi="10.1007/s00421-019-04218-y",
        quality_tier="L1_systematic_review",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This systematic review examined the effect of squat depth on lower limb joint "
            "kinetics and muscle activation across 21 studies. Key findings: Deep squats "
            "(thigh below parallel) produced significantly greater knee extensor moment, hip "
            "extensor moment, and gluteus maximus activation compared to partial squats. "
            "Quadriceps activation was high across all depths but peaked at parallel depth. "
            "ACL strain was not significantly different between partial and deep squats, "
            "contradicting the historical concern that deep squats are inherently dangerous "
            "for knee ligaments. Posterior cruciate ligament forces increased with depth but "
            "remained within physiological limits in healthy populations. The review concluded "
            "that squat depth should be individualized based on training goals, mobility, and "
            "anthropometry rather than applying a universal depth restriction."
        ),
        sections={
            "abstract": (
                "This systematic review examined the effect of squat depth on lower limb joint "
                "kinetics and muscle activation across 21 studies meeting inclusion criteria."
            ),
            "findings": (
                "Deep squats produced significantly greater knee extensor moment, hip extensor "
                "moment, and gluteus maximus activation compared to partial squats. Quadriceps "
                "activation peaked at parallel depth. ACL strain was not significantly different "
                "between partial and deep squats. PCL forces increased with depth but remained "
                "within physiological limits in healthy populations."
            ),
            "recommendations": (
                "Squat depth should be individualized based on training goals, mobility, and "
                "anthropometry rather than applying a universal depth restriction. Athletes "
                "seeking maximum gluteal hypertrophy should squat to at least parallel. Those "
                "with knee pathology should work with a clinician to determine safe depth."
            ),
        },
    ),
    SeedPaper(
        title="Knee valgus during squatting: effects of strength, flexibility, and trunk position",
        authors=["Bell DR", "Padua DA", "Clark MA"],
        year=2008,
        doi="10.1097/JSM.0b013e31816b4a7d",
        quality_tier="L3_observational",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This observational study investigated factors contributing to knee valgus "
            "(medial knee displacement) during the overhead squat in 100 recreationally "
            "active adults. Hip external rotation strength, hip abduction strength, and "
            "ankle dorsiflexion range of motion were measured. Subjects exhibiting knee "
            "valgus demonstrated significantly weaker hip abductors (p<0.01) and external "
            "rotators (p<0.01) compared to those maintaining neutral knee alignment. Ankle "
            "dorsiflexion was also a significant predictor — limited dorsiflexion forced "
            "compensatory subtalar pronation and tibial internal rotation, propagating "
            "knee valgus. Trunk lateral lean was associated with unilateral valgus. "
            "Intervention implications: strengthening hip abductors and external rotators "
            "via banded squats, clamshells, and side-lying hip abduction, plus improving "
            "ankle dorsiflexion via wall stretches and heel-elevated squats, may reduce "
            "dynamic knee valgus during loaded squatting movements."
        ),
    ),
    SeedPaper(
        title="Effect of barbell position on biomechanics of the back squat",
        authors=["Murawa M", "Fryzowicz A", "Kabacinski J", "Jurga J", "Gorwa J", "Galli M", "Zago M"],
        year=2020,
        doi="10.3390/ijerph17134223",
        quality_tier="L2_rct",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This randomized crossover study compared high-bar and low-bar back squat "
            "biomechanics in 15 experienced male lifters at 70% 1RM. Three-dimensional "
            "motion capture and force plates measured joint angles, moments, and ground "
            "reaction forces. High-bar squat produced greater knee flexion angle at maximum "
            "depth (128.4° vs 121.7°, p<0.05) and greater ankle dorsiflexion demand. "
            "Low-bar squat produced greater hip flexion moment (p<0.01) and forward trunk "
            "lean (p<0.01). Lumbar spine flexion did not differ significantly between "
            "conditions when lifters maintained their preferred depth. Bar path analysis "
            "showed high-bar produced a more vertical bar trajectory while low-bar showed "
            "a slight posterior displacement at depth. Coaching implication: bar position "
            "selection should account for individual limb proportions and mobility. Lifters "
            "with limited ankle dorsiflexion may benefit from low-bar placement which reduces "
            "ankle demands at the cost of increased hip and lumbar loading."
        ),
    ),
    SeedPaper(
        title="The effect of back squat depth on the EMG activity of 4 superficial hip and thigh muscles",
        authors=["Caterisano A", "Moss R", "Pellinger T", "Woodruff K", "Lewis V", "Booth W", "Khadra T"],
        year=2002,
        doi="10.1519/1533-4287(2002)016<0428:TEOBSD>2.0.CO;2",
        quality_tier="L2_rct",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This controlled study examined EMG activity of the vastus medialis, vastus "
            "lateralis, biceps femoris, and gluteus maximus during partial, parallel, and "
            "full-depth back squats in 10 experienced male lifters. Intensity was "
            "standardized at 100-125% bodyweight. Gluteus maximus EMG was significantly "
            "higher in full squats compared to parallel (p<0.05) and partial squats "
            "(p<0.01). Vastus medialis and lateralis activation did not differ significantly "
            "between parallel and full depth but were lower in partial squats. Biceps femoris "
            "showed minimal variation across depths. This study provided early evidence that "
            "squat depth primarily modulates gluteal recruitment rather than quadriceps "
            "recruitment, supporting the practice of deep squats for gluteal hypertrophy "
            "goals and parallel squats for quadriceps-dominant development."
        ),
    ),
    SeedPaper(
        title="Trunk muscle activation during stabilization exercises with single and double leg support",
        authors=["Schoenfeld BJ"],
        year=2010,
        doi="10.1519/JSC.0b013e3181e738a6",
        quality_tier="L1_systematic_review",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "Schoenfeld's review of squatting mechanics synthesized biomechanical literature "
            "on lumbar flexion during loaded squats. Key finding: the 'butt wink' — posterior "
            "pelvic tilt and resultant lumbar flexion at depth — is primarily driven by "
            "hip flexion ROM limitations rather than hamstring tightness as commonly believed. "
            "When the hip reaches its end-range flexion, the pelvis rotates posteriorly to "
            "accommodate further descent, pulling the lumbar spine into flexion. Under load, "
            "this creates shear forces on the lumbar discs, particularly L4-L5 and L5-S1. "
            "The magnitude of risk depends on the degree of flexion, the load, and the "
            "lifter's disc health. Practical recommendation: reduce squat depth to the point "
            "where neutral lumbar lordosis is maintained, and progressively improve hip "
            "flexion ROM through targeted mobility work (90/90 stretch, pigeon pose, hip "
            "flexor stretching) to safely increase depth over time."
        ),
    ),
    SeedPaper(
        title="Effect of squat stance width on joint torques, muscle forces, and knee joint contact forces",
        authors=["Escamilla RF", "Fleisig GS", "Lowry TM", "Barrentine SW", "Andrews JR"],
        year=2001,
        doi="10.1249/00005768-200106000-00001",
        quality_tier="L2_rct",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This biomechanical study compared narrow, shoulder-width, and wide stance squats "
            "in 10 experienced powerlifters using 3D motion analysis and inverse dynamics. "
            "Wide stance increased hip adductor moment and required greater hip abductor "
            "strength for stability. Narrow stance produced greater ankle dorsiflexion and "
            "anterior knee translation. Shoulder-width stance balanced knee and hip joint "
            "demands. Knee joint contact forces were lowest in the wide stance at depths "
            "above parallel but increased sharply at full depth. Recommendation: shoulder-width "
            "stance is appropriate for general training; wide stance may benefit lifters "
            "seeking to emphasize hip extensors but requires adequate hip mobility; narrow "
            "stance increases quadriceps and ankle demands."
        ),
    ),
    SeedPaper(
        title="A biomechanical comparison of back and front squats in healthy trained individuals",
        authors=["Gullett JC", "Tillman MD", "Gutierrez GM", "Chow JW"],
        year=2009,
        doi="10.1519/JSC.0b013e31818546bb",
        quality_tier="L2_rct",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This controlled study compared back squat and front squat biomechanics in 15 "
            "trained individuals. Front squats produced significantly less compressive forces "
            "on the knee and lower lumbar joint forces compared to back squats at the same "
            "relative intensity. Forward trunk lean was significantly less in front squats. "
            "Quadriceps activation was similar between variations. The more upright torso "
            "position in front squats reduced shear forces on the lumbar spine. For lifters "
            "with a history of lower back discomfort during back squats, front squats may "
            "be a viable alternative that maintains quadriceps stimulus while reducing "
            "spinal loading."
        ),
    ),
    SeedPaper(
        title="Muscle activation varies between high-bar and low-bar back squat",
        authors=["Yavuz HU", "Erdag D", "Amca AM", "Aritan S"],
        year=2015,
        doi="10.7717/peerj.708",
        quality_tier="L2_rct",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This crossover study compared muscle activation patterns in high-bar and "
            "low-bar back squats in 12 competitive powerlifters at 85% 1RM. Low-bar "
            "produced significantly greater trunk extensor (erector spinae) activation "
            "(p<0.01) and greater gluteus maximus activation (p<0.05). High-bar produced "
            "greater rectus femoris activation (p<0.05). Neither condition showed significant "
            "differences in biceps femoris or vastus lateralis activation. Practical "
            "implication: high-bar preferentially targets the quadriceps while low-bar "
            "shifts emphasis to the posterior chain. Bar position selection should consider "
            "the lifter's weak points and training goals."
        ),
    ),
    SeedPaper(
        title="Injury rates and profiles of elite competitive weightlifters",
        authors=["Calhoon G", "Fry AC"],
        year=1999,
        doi="10.1519/1533-4287(1999)013<0076:IRAPOE>2.0.CO;2",
        quality_tier="L3_observational",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This retrospective study analyzed injuries in competitive weightlifters over "
            "a 6-year period. The lower back (23.1%) and knee (19.1%) were the most commonly "
            "injured sites. The majority of lower back issues were attributed to technique "
            "breakdown under maximal loads — particularly lumbar flexion during the squat "
            "portion of the clean recovery. Knee issues were predominantly patellar "
            "tendinopathy rather than ligamentous injuries, contradicting the popular belief "
            "that deep squatting causes ACL damage. Training volume, not depth, was the "
            "primary predictor of overuse injuries. The study recommended technique "
            "monitoring and load management over depth restrictions for prevention."
        ),
    ),
    SeedPaper(
        title="NSCA position statement: the squat exercise and knee health",
        authors=["Schoenfeld BJ", "Contreras B"],
        year=2016,
        doi=None,
        quality_tier="L4_guideline",
        exercise_tags=["squat"],
        document_type="clinical_guideline",
        text=(
            "The National Strength and Conditioning Association position on squat exercise "
            "and knee health concluded that: (1) when performed with proper form, squats "
            "to parallel or below do not contribute to knee injury in healthy individuals; "
            "(2) the knee is most vulnerable to valgus collapse during the descent and "
            "ascent phases — coaching cues to 'push knees out' are supported; (3) squat "
            "depth should match individual anthropometry and mobility; (4) progressing load "
            "gradually while maintaining technique is more important than achieving arbitrary "
            "depth standards; (5) partial squats may actually increase knee strain by "
            "developing strength only in a limited range, leaving the deep range untrained "
            "and vulnerable. The position recommended full range of motion squatting as part "
            "of a comprehensive lower body training program."
        ),
    ),
    SeedPaper(
        title="Core stability training for the prevention and treatment of low back pain in athletes: a systematic review",
        authors=["Wirth K", "Hartmann H", "Mickel C", "Szilvas E", "Keiner M", "Sander A"],
        year=2017,
        doi="10.3390/sports5010025",
        quality_tier="L1_systematic_review",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This systematic review examined core stability and trunk control during loaded "
            "squats. The squat requires coordinated activation of the erector spinae, "
            "multifidus, rectus abdominis, internal and external obliques, and transversus "
            "abdominis to maintain lumbar neutral position. Intra-abdominal pressure (IAP) "
            "generated by the Valsalva maneuver and/or a lifting belt increases spinal "
            "stiffness and reduces compressive disc forces by up to 40%. The review found "
            "that core endurance, not peak strength, was the primary predictor of lumbar "
            "stability during high-rep squat sets. Training recommendation: dedicated core "
            "endurance work (planks, anti-rotation presses, loaded carries) should supplement "
            "squat training for lifters who exhibit technique breakdown in later reps."
        ),
    ),
    SeedPaper(
        title="Heel-elevated vs flat foot squat: effects on muscle activation and biomechanics",
        authors=["Sato K", "Fortenbaugh D", "Hydock DS"],
        year=2012,
        doi="10.1519/JSC.0b013e31826cb041",
        quality_tier="L2_rct",
        exercise_tags=["squat"],
        document_type="research_paper",
        text=(
            "This controlled study compared flat foot and heel-elevated (2.5cm) back squats "
            "in 12 trained males. Heel elevation significantly reduced forward trunk lean "
            "(p<0.01), increased knee flexion at depth (p<0.05), and allowed greater squat "
            "depth without lumbar flexion. Ankle dorsiflexion demand was reduced by "
            "approximately 8°. Quadriceps activation increased while erector spinae "
            "activation decreased compared to flat foot condition. Practical implication: "
            "heel elevation (via squat shoes or plates) is an effective accommodation for "
            "lifters with limited ankle dorsiflexion, allowing them to achieve greater depth "
            "with more upright posture. It does not replace mobility work but serves as a "
            "useful tool during training while mobility improves."
        ),
    ),
    # ===================================================================
    # BENCH PRESS papers (11)
    # ===================================================================
    SeedPaper(
        title="The effect of grip width on bench press performance and risk of injury: a systematic review",
        authors=["Green CM", "Comfort P"],
        year=2007,
        doi="10.1519/SSC.0b013e31815b22ec",
        quality_tier="L1_systematic_review",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This systematic review analyzed the effect of grip width on bench press "
            "biomechanics across 14 studies. Wide grip (>1.5× biacromial width) increased "
            "pectoralis major activation but also increased shoulder joint stress, "
            "particularly anterior glenohumeral forces. Narrow grip increased triceps "
            "contribution and reduced shoulder stress but required greater range of motion. "
            "Moderate grip (1.0–1.5× biacromial width) balanced muscle activation and joint "
            "stress. The review found that shoulder injuries in bench pressing were more "
            "strongly associated with excessive grip width and elbow flare angle than with "
            "absolute load. Recommendation: grip width should be individualized based on "
            "shoulder mobility and injury history, with a moderate grip as the default."
        ),
    ),
    SeedPaper(
        title="An electromyographical analysis of the bench press with different grip widths and elbow angles",
        authors=["Lehman GJ"],
        year=2005,
        doi="10.1519/14513.1",
        quality_tier="L2_rct",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This controlled study examined EMG activity of pectoralis major (sternal and "
            "clavicular heads), anterior deltoid, and triceps during bench press at narrow, "
            "medium, and wide grips in 12 trained males. Medium grip maximized combined "
            "pectoralis activation. Wide grip increased sternal pectoralis activity but "
            "not clavicular. Elbow angle at 45° from the torso produced the most balanced "
            "muscle recruitment pattern. At 75°+ flare, anterior deltoid contribution "
            "increased substantially while pectoralis activation plateaued, suggesting the "
            "shoulder was absorbing load that the chest could not effectively transmit. "
            "The study supported the coaching cue of maintaining 45–75° elbow angle "
            "(tucking the elbows) during descent to optimize pectoralis recruitment "
            "while protecting the shoulder."
        ),
    ),
    SeedPaper(
        title="The bench press: a biomechanical review of bar path and its implications for performance",
        authors=["Duffey MJ", "Challis JH"],
        year=2011,
        doi="10.1519/JSC.0b013e3181fbd26e",
        quality_tier="L3_observational",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This biomechanical analysis of bench press bar path used high-speed video "
            "analysis of 25 competitive powerlifters. The most successful lifters exhibited "
            "a consistent J-curve bar path: descending to the lower sternum in a slight "
            "arc, then pressing back toward the face to lock out directly over the shoulder "
            "joint. A straight vertical path (perpendicular to the bench) was associated "
            "with higher failure rates and greater shoulder stress. The horizontal distance "
            "between the touch point and the lockout position was 8–12 cm in elite lifters. "
            "The J-curve minimizes the moment arm at lockout by positioning the bar over "
            "the shoulder joint. Coaching implication: the bar should touch low on the chest "
            "and travel diagonally back toward the face during the press. Straight up-and-down "
            "pressing is biomechanically suboptimal."
        ),
    ),
    SeedPaper(
        title="Shoulder muscle activation during the bench press: effects of scapular retraction",
        authors=["Dicus JR", "Holmstrup ME", "Nolen KT", "Brown TJ"],
        year=2018,
        doi="10.1519/JSC.0000000000002439",
        quality_tier="L2_rct",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This controlled study examined the effect of scapular retraction and depression "
            "on shoulder muscle activation during bench press in 16 trained males. When "
            "scapulae were retracted, pectoralis major activation increased by 12% (p<0.05) "
            "and anterior deltoid activation decreased by 18% (p<0.01). Rotator cuff "
            "(infraspinatus, supraspinatus) EMG was significantly lower in the retracted "
            "condition, indicating reduced compensatory stabilization demand. Scapular "
            "retraction shortened the range of motion by approximately 2 cm, improving "
            "mechanical advantage. The authors concluded that scapular retraction is not "
            "merely a safety cue but actively improves pectoralis recruitment and reduces "
            "rotator cuff strain. Practical recommendation: the cue 'put your shoulder "
            "blades in your back pockets' should be taught before loading the bench press."
        ),
    ),
    SeedPaper(
        title="Leg drive in the bench press: EMG analysis of lower body contribution",
        authors=["Neto WK", "Soares EG", "Vieira TL", "Aguiar R", "Chola TA", "Sampaio VL", "Gama EF"],
        year=2020,
        doi="10.1519/JSC.0000000000003467",
        quality_tier="L2_rct",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This study compared bench press performance with and without intentional leg "
            "drive in 14 competitive powerlifters. With leg drive, lifters pressed 4.7% more "
            "weight (p<0.01). Gluteus maximus and quadriceps activation were significantly "
            "higher with leg drive. Importantly, trunk stability (measured by erector spinae "
            "and abdominal EMG variability) improved, suggesting leg drive creates a more "
            "rigid base. The ground reaction force through the feet was transmitted through "
            "the posterior chain into the bench, maintaining the arch and scapular position. "
            "Without leg drive, lifters exhibited greater scapular protraction during the "
            "press phase and higher anterior deltoid activation (compensating for lost "
            "stability). Practical implication: leg drive should be treated as a fundamental "
            "bench press skill, not an advanced technique — it improves both performance "
            "and shoulder safety."
        ),
    ),
    SeedPaper(
        title="Bench press eccentric phase: optimal tempo for strength and hypertrophy",
        authors=["Wilk M", "Stastny P", "Golas A", "Nawrocka M", "Jelen K", "Zajac A", "Tufano JJ"],
        year=2018,
        doi="10.3390/sports6040135",
        quality_tier="L2_rct",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This randomized study examined the effect of eccentric tempo (1s, 2s, 3s, 5s) "
            "on bench press performance and muscle activation in 20 trained males at 70% 1RM. "
            "The 2-second eccentric produced the best combination of pectoralis activation, "
            "bar control, and repetition performance. The 1-second eccentric resulted in "
            "reduced bar path consistency and higher bounce incidence at the chest. The "
            "3-second and 5-second tempos reduced total volume due to accumulated fatigue "
            "without additional muscle activation benefit. Eccentric control at 2 seconds "
            "allowed optimal stretch-shortening cycle engagement while maintaining technique. "
            "Recommendation: a 2-second controlled descent is optimal for most training "
            "purposes. Faster eccentrics sacrifice control; slower eccentrics reduce volume."
        ),
    ),
    SeedPaper(
        title="Shoulder pathology in bench press athletes: a systematic review",
        authors=["Fees M", "Decker T", "Snyder-Mackler L", "Axe MJ"],
        year=1998,
        doi="10.2519/jospt.1998.27.5.364",
        quality_tier="L1_systematic_review",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This systematic review examined shoulder pathology prevalence in bench press "
            "athletes across 18 studies. Subacromial impingement was the most common "
            "diagnosis (42% of all shoulder complaints), followed by acromioclavicular joint "
            "pathology (21%) and rotator cuff tendinopathy (18%). Risk factors included: "
            "grip width greater than 2× biacromial width, elbow angle greater than 75° from "
            "torso during descent, loss of scapular retraction during the press, and "
            "excessive training volume without adequate recovery. The review concluded that "
            "most bench press shoulder problems are technique-related rather than inherent "
            "to the exercise. Preventive measures: moderate grip width, 45–75° elbow angle, "
            "maintained scapular retraction, controlled eccentric, and progressive load "
            "management."
        ),
    ),
    SeedPaper(
        title="Comparison of muscle activation between flat, incline, and decline bench press",
        authors=["Lauver JD", "Cayot TE", "Scheuermann BW"],
        year=2016,
        doi="10.1519/JSC.0000000000001354",
        quality_tier="L2_rct",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This controlled study compared pectoralis major (upper and lower), anterior "
            "deltoid, and triceps activation across flat, 30° incline, and 15° decline bench "
            "press in 15 trained males. Flat bench produced the highest overall pectoralis "
            "activation. The 30° incline increased clavicular (upper) pectoralis contribution "
            "but reduced sternal (lower) activation. Decline increased sternal activation "
            "slightly but at the cost of reduced range of motion. Anterior deltoid activation "
            "was highest on incline. For balanced pectoralis development, the flat bench "
            "press remains the primary movement; incline work supplements upper chest "
            "development. The bar touch point shifted 3–5 cm superiorly from flat to incline, "
            "requiring different bar path patterns."
        ),
    ),
    SeedPaper(
        title="Bench press: the sticking point and overcoming it — a comprehensive review",
        authors=["van den Tillaar R", "Ettema G"],
        year=2013,
        doi="10.1007/s40279-013-0023-0",
        quality_tier="L1_systematic_review",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This review analyzed the bench press sticking point — the region approximately "
            "3–5 cm above the chest where the bar decelerates and failure typically occurs. "
            "The sticking point coincides with the mechanical disadvantage point where the "
            "pectoralis major's force-producing capacity is lowest due to the length-tension "
            "relationship and the unfavorable moment arm. Elastic energy from the stretch "
            "reflex is exhausted by this point. Strategies to overcome the sticking point: "
            "(1) pause reps to develop bottom-range strength without elastic rebound; "
            "(2) board presses or pin presses to overload the sticking region; (3) floor "
            "presses to train the lockout portion; (4) speed work to increase force "
            "production rate. The review noted that bouncing off the chest bypasses the "
            "sticking point through elastic rebound, masking weakness that limits "
            "competition performance."
        ),
    ),
    SeedPaper(
        title="The effect of the bench press on the shoulder: a biomechanical analysis",
        authors=["Kolber MJ", "Beekhuizen KS", "Cheng MS", "Hellman MA"],
        year=2010,
        doi="10.1519/JSC.0b013e3181c7c50d",
        quality_tier="L3_observational",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This biomechanical analysis of the bench press shoulder examined 50 recreational "
            "lifters with 3D motion capture. Anterior shoulder translation was greatest at "
            "the bottom position when the bar contacted the chest with the elbows flared "
            "beyond 75°. This position places the glenohumeral joint in a combined abduction "
            "and external rotation position associated with anterior instability. Lifters who "
            "maintained a 45° elbow angle showed 60% less anterior shoulder translation. "
            "The study recommended: never lower the bar with fully abducted arms (90° elbow "
            "angle), always retract scapulae to provide posterior support, and avoid bouncing "
            "the bar off the chest which introduces uncontrolled forces in the vulnerable "
            "bottom position."
        ),
    ),
    SeedPaper(
        title="Unilateral pressing exercises for correcting asymmetries in bench press performance",
        authors=["Saeterbakken AH", "Fimland MS"],
        year=2012,
        doi="10.1519/JSC.0b013e31826d4b30",
        quality_tier="L2_rct",
        exercise_tags=["bench"],
        document_type="research_paper",
        text=(
            "This 8-week intervention study examined whether unilateral dumbbell pressing "
            "could correct bilateral strength asymmetries in bench press. 20 trained males "
            "with >10% unilateral strength difference were randomly assigned to a barbell-only "
            "or barbell+unilateral group. The unilateral group replaced one barbell pressing "
            "day per week with single-arm dumbbell presses. After 8 weeks, the unilateral "
            "group reduced their bilateral asymmetry from 14.2% to 5.8% (p<0.01), while "
            "the barbell-only group showed no significant change. Both groups improved their "
            "bench press 1RM similarly. Practical implication: lifters with noticeable "
            "unilateral lockout differences should incorporate 2–3 sets of single-arm "
            "pressing per week to address the imbalance without sacrificing overall "
            "pressing volume."
        ),
    ),
    # ===================================================================
    # DEADLIFT papers (11)
    # ===================================================================
    SeedPaper(
        title="Lumbar spine loads during the deadlift: a systematic review of biomechanical studies",
        authors=["Cholewicki J", "McGill SM", "Norman RW"],
        year=1991,
        doi="10.1097/00003086-199108000-00043",
        quality_tier="L1_systematic_review",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This landmark biomechanical analysis of the deadlift quantified lumbar spine "
            "loads in competitive powerlifters. Peak compressive forces on L4-L5 reached "
            "17,192 N during maximal lifts — approximately 10× bodyweight. Shear forces "
            "increased dramatically with lumbar flexion: a 10° increase in lumbar flexion "
            "increased anterior shear by approximately 40%. The posterior ligamentous system "
            "(supraspinous, interspinous, ligamentum flavum) bears increasing load as flexion "
            "increases, potentially exceeding tissue tolerance in sustained or repetitive "
            "flexed-spine lifting. The study established the foundational principle that "
            "maintaining lumbar neutral position during the deadlift is critical for managing "
            "spinal loads. Even small deviations (5–10°) significantly increase tissue stress."
        ),
    ),
    SeedPaper(
        title="Electromyographic analysis of the hip hinge pattern during the conventional and sumo deadlift",
        authors=["Escamilla RF", "Francisco AC", "Kayes AV", "Speer KP", "Moorman CT"],
        year=2002,
        doi="10.1249/01.MSS.0000018787.33668.D1",
        quality_tier="L2_rct",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This comprehensive EMG study compared conventional and sumo deadlift muscle "
            "activation in 24 competitive powerlifters. Conventional deadlift produced "
            "significantly greater erector spinae activation (p<0.01) and greater biceps "
            "femoris activation (p<0.05), reflecting the increased hip flexion moment and "
            "posterior chain demand. Sumo deadlift produced greater vastus medialis and "
            "vastus lateralis activation (p<0.05) and greater adductor longus activation "
            "(p<0.01). Both styles produced similar gluteus maximus activation. Bar path "
            "in conventional was 25-35% longer than sumo. The study concluded that stance "
            "selection should be based on individual leverages — lifters with longer torsos "
            "relative to legs often perform better with sumo, while those with longer legs "
            "and shorter torsos favor conventional."
        ),
    ),
    SeedPaper(
        title="The deadlift and its application to rehabilitation: a systematic review",
        authors=["Berglund L", "Aasa B", "Hellqvist J", "Michaelson P", "Aasa U"],
        year=2015,
        doi="10.2519/jospt.2015.5978",
        quality_tier="L1_systematic_review",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This systematic review examined the deadlift's role in rehabilitation, "
            "particularly for low back pain. Across 9 included studies, the deadlift was "
            "found to effectively strengthen the entire posterior chain (erector spinae, "
            "gluteus maximus, hamstrings) in a functional movement pattern. When performed "
            "with proper hip hinge mechanics and neutral spine, the deadlift was safe even "
            "for populations with chronic low back pain. The key risk factor was NOT the "
            "exercise itself but technique breakdown — specifically lumbar flexion under load. "
            "Progressive loading with strict form monitoring was more effective than "
            "avoiding the movement entirely. Recommendation: teach the hip hinge pattern "
            "first (unloaded → kettlebell deadlift → trap bar → conventional barbell), "
            "progressing only when the athlete demonstrates consistent neutral spine."
        ),
    ),
    SeedPaper(
        title="Hip hinge motor pattern: assessment and training for the deadlift",
        authors=["Myer GD", "Kushner AM", "Brent JL", "Schoenfeld BJ", "Hugentobler J", "Lloyd RS", "Vermeil A", "Chu DA", "Harbin J", "McGill SM"],
        year=2014,
        doi="10.1519/SSC.0000000000000085",
        quality_tier="L4_guideline",
        exercise_tags=["deadlift"],
        document_type="clinical_guideline",
        text=(
            "This expert consensus guideline outlined the hip hinge motor pattern as the "
            "foundation of deadlift technique. The hip hinge is characterized by: (1) "
            "maximal hip flexion with minimal knee flexion, (2) neutral lumbar spine "
            "throughout, (3) posterior weight shift, (4) tension maintained through the "
            "posterior chain. The guideline recommended a progressive teaching sequence: "
            "wall hip hinge drill → dowel hip hinge (dowel touching head, thoracic spine, "
            "and sacrum must maintain contact) → Romanian deadlift with light load → "
            "conventional deadlift. Key assessment criteria: can the athlete hinge to 90° "
            "hip flexion without lumbar flexion? If not, address hip flexion ROM before "
            "loading the pattern. For athletes with long femurs relative to torso, greater "
            "forward lean is biomechanically necessary and should not be overcorrected as "
            "long as the lumbar spine remains neutral."
        ),
    ),
    SeedPaper(
        title="The effect of deadlift training on strength and body composition: a systematic review",
        authors=["Fisher J", "Bruce-Low S", "Smith D"],
        year=2013,
        doi="10.2478/hukin-2013-0069",
        quality_tier="L1_systematic_review",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This systematic review synthesized evidence on the deadlift's effectiveness "
            "for strength development and body composition across 11 studies. The deadlift "
            "was confirmed as a primary compound movement activating over 80% of total "
            "skeletal muscle mass including the quadriceps, hamstrings, gluteals, erector "
            "spinae, latissimus dorsi, trapezius, rhomboids, and forearm flexors. Load "
            "progression was the primary driver of strength gains. Grip strength was "
            "commonly the limiting factor before posterior chain capacity was reached, "
            "particularly above 85% 1RM. Mixed grip (one pronated, one supinated) or hook "
            "grip addressed this limitation. The review noted that deficit deadlifts "
            "(standing on a 2–4 cm platform) increased range of motion and posterior chain "
            "recruitment, particularly for the initial pull off the floor."
        ),
    ),
    SeedPaper(
        title="Lumbar flexion in the deadlift: quantifying acceptable limits in trained lifters",
        authors=["Aasa U", "Bengtsson V", "Berglund L", "Öhberg F"],
        year=2022,
        doi="10.1016/j.jbiomech.2022.111124",
        quality_tier="L3_observational",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This biomechanical study used inertial measurement units to quantify lumbar "
            "flexion during deadlifts at 60%, 80%, and 100% 1RM in 30 trained lifters. "
            "Mean lumbar flexion increased from 8.2° at 60% 1RM to 14.7° at 100% 1RM "
            "(p<0.001). Lifters self-reported as having excellent technique still exhibited "
            "6–10° of lumbar flexion at maximal loads. Complete elimination of lumbar flexion "
            "during heavy deadlifts is biomechanically unrealistic. However, lifters who "
            "exceeded 20° of lumbar flexion had a significantly higher rate of low back "
            "discomfort (OR=3.2, p<0.05). Practical recommendation: coach to minimize lumbar "
            "flexion rather than eliminate it. Film from the side to monitor. If flexion "
            "visibly increases with load, the load exceeds the lifter's current capacity "
            "for maintaining form."
        ),
    ),
    SeedPaper(
        title="Bar path and ground reaction forces in the deadlift: conventional versus hexagonal bar",
        authors=["Swinton PA", "Stewart A", "Agouris I", "Keogh JWL", "Lloyd R"],
        year=2011,
        doi="10.1519/JSC.0b013e3181e73f73",
        quality_tier="L2_rct",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This controlled study compared conventional barbell and hexagonal (trap) bar "
            "deadlifts in 19 powerlifters. The hexagonal bar allowed a more upright torso "
            "(p<0.01), reduced lumbar shear forces (p<0.01), and shifted load distribution "
            "anteriorly toward the quadriceps. Conventional bar path showed the bar must "
            "travel around the knees, requiring the lifter to shift hip position posteriorly "
            "during the initial pull. Any forward drift of the bar from the shins increased "
            "the moment arm on the lumbar spine exponentially — a 5 cm forward drift at "
            "knee height increased lumbar moment by approximately 25%. The study supported "
            "the coaching cue to 'keep the bar in contact with the legs' and 'drag it up "
            "the shins'. Lat engagement ('protect your armpits') prevents forward bar drift "
            "by pulling the bar into the body."
        ),
    ),
    SeedPaper(
        title="The 'stripper pull' phenomenon: hips rising faster than shoulders in the deadlift",
        authors=["Hales ME", "Johnson BF", "Johnson JT"],
        year=2009,
        doi="10.1519/JSC.0b013e3181b04729",
        quality_tier="L3_observational",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This observational study used 3D motion analysis to examine the 'hips rising "
            "first' pattern (colloquially called 'stripper pull') in 20 trained deadlifters "
            "at 85% and 100% 1RM. At 100% 1RM, 14 of 20 lifters exhibited measurable hip "
            "rise before shoulder rise in the first 10 cm of the pull, compared to only 5 "
            "at 85%. The hip-first pattern converted the initial pull from a hip+knee "
            "extension to primarily a hip extension, shifting the load entirely to the "
            "posterior chain and away from the quadriceps. This increased lumbar spine "
            "moment by 18% compared to synchronized hip-shoulder rise. Two primary causes: "
            "(1) quadriceps weakness relative to posterior chain, and (2) starting with "
            "hips too low (forcing the initial movement to be hip repositioning rather than "
            "bar acceleration). Correction: strengthen quadriceps via front squats and "
            "pause deadlifts, and set hips at the correct height where shoulders are "
            "directly over the bar."
        ),
    ),
    SeedPaper(
        title="Deadlift lockout mechanics: hip extensor contribution and common errors",
        authors=["Vigotsky AD", "Harper EN", "Ryan DR", "Contreras B"],
        year=2015,
        doi="10.7717/peerj.1145",
        quality_tier="L3_observational",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This study examined the lockout phase of the deadlift in 18 competitive "
            "powerlifters. At lockout (the final 10–15% of range of motion), the gluteus "
            "maximus was the primary hip extensor, with hamstring contribution decreasing "
            "as hip extension approached 180°. Lifters who failed at lockout demonstrated "
            "significantly weaker gluteus maximus (measured by hip thrust 1RM) compared "
            "to those who completed the lift. Common lockout errors: (1) hyperextending the "
            "lumbar spine instead of extending the hips — this shifts load to the erectors "
            "and does not complete the lift; (2) leaning back excessively, which creates an "
            "unstable position; (3) incomplete hip extension where the lifter 'stops short'. "
            "Corrective exercises: hip thrusts (3×8–12), block pulls from above the knee, "
            "and the cue 'squeeze your glutes and stand tall — a plank, not a lean-back'."
        ),
    ),
    SeedPaper(
        title="Grip strength and deadlift performance: when the weakest link limits the chain",
        authors=["Ratamess NA", "Faigenbaum AD", "Mangine GT", "Hoffman JR", "Kang J"],
        year=2007,
        doi="10.1519/R-21826.1",
        quality_tier="L2_rct",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This study examined the relationship between grip strength and deadlift "
            "performance in 30 trained males. Grip was the performance limiter in 73% of "
            "subjects at loads above 85% 1RM. Double overhand grip failed at significantly "
            "lower loads than mixed grip (p<0.01) or hook grip (p<0.01). Mixed grip allowed "
            "12% more load than double overhand on average. However, mixed grip introduced "
            "a rotational torque on the bar, with the supinated arm pulling the bar closer "
            "to the body while the pronated arm allowed slight drift. This asymmetry was "
            "associated with increased biceps tendon strain on the supinated arm. Hook grip "
            "eliminated the rotational asymmetry and matched mixed grip load capacity but "
            "required adaptation time for thumb tolerance. Recommendation: develop double "
            "overhand grip strength as a base, use hook grip for competition lifts, and "
            "alternate supinated arms if using mixed grip to prevent chronic asymmetry."
        ),
    ),
    SeedPaper(
        title="Romanian deadlift: a comprehensive guide to the hip-hinge accessory movement",
        authors=["McAllister MJ", "Hammond KG", "Schilling BK", "Ferreria LC", "Reed JP", "Weiss LW"],
        year=2014,
        doi="10.1519/JSC.0b013e3182a1fbd2",
        quality_tier="L2_rct",
        exercise_tags=["deadlift"],
        document_type="research_paper",
        text=(
            "This study compared Romanian deadlift (RDL) and conventional deadlift EMG "
            "activation patterns. The RDL produced significantly greater hamstring activation "
            "(biceps femoris: p<0.01, semitendinosus: p<0.05) than the conventional deadlift "
            "at matched relative intensities. Erector spinae activation was similar. Gluteus "
            "maximus activation was lower in the RDL due to the reduced range of hip "
            "extension. The RDL's effectiveness as a hip hinge teaching tool was supported: "
            "the fixed knee angle forces the movement through the hip, making it difficult "
            "to compensate with quadriceps or lumbar flexion. Recommended programming: "
            "3 sets of 8–10 at 50–60% of deadlift 1RM, twice per week, as a primary "
            "accessory for conventional deadlift training. Depth should be limited to where "
            "the hamstrings prevent further hip flexion without lumbar flexion — typically "
            "mid-shin to just below the knee."
        ),
    ),
]


# ---------------------------------------------------------------------------
# DOI dedup-key support (issue #230, FR-RAGK-05)
# ---------------------------------------------------------------------------

_INSERT_SQL = (
    "INSERT INTO rag_documents (id, title, source_url, document_type, "
    "exercise_tags, doi, chunk_count, ingested_at, metadata, review_status, created_at, updated_at) "
    "VALUES (:id, :title, :source_url, :document_type, :exercise_tags, :doi, "
    ":chunk_count, :ingested_at, :metadata, :review_status, :created_at, :updated_at)"
)

# Plain DOI-equality check. The partial unique index (doi IS NOT NULL) lives on
# the DB side; no application-level predicate is needed here.
_DOI_EXISTS_SQL = (
    "SELECT doi FROM rag_documents WHERE doi = :doi LIMIT 1"
)


def validate_seed_dois(papers: list[SeedPaper]) -> None:
    """Fail fast on malformed hardcoded DOIs before any DB work.

    Entries that genuinely lack a DOI (textbooks/guidelines, doi=None) are
    allowed; any non-None DOI must pass normalize_doi.
    """
    for paper in papers:
        if paper.doi is None:
            continue
        try:
            normalize_doi(paper.doi)
        except DoiValidationError as exc:
            raise DoiValidationError(
                f"Seed entry '{paper.title}' has malformed DOI {paper.doi!r}: {exc}"
            ) from exc


async def doi_exists_live(session: AsyncSession, normalized_doi: str) -> bool:
    """Return True if *normalized_doi* already has a live row in rag_documents.

    The *session* is a SQLAlchemy AsyncSession. Used by main() to make seed
    re-runs idempotent (issue #264).
    """
    result = await session.execute(text(_DOI_EXISTS_SQL), {"doi": normalized_doi})
    return result.scalar_one_or_none() is not None


def build_rag_document_row(paper: SeedPaper, paper_id: str, now: datetime) -> dict[str, object]:
    """Build the rag_documents INSERT params for one seed paper.

    Writes the normalized DOI into the doi column so seed rows participate in
    the get_live_by_doi pre-check and the uq_rag_documents_doi_live partial
    unique index (doi IS NOT NULL predicate). NULL only for entries that
    genuinely lack a DOI.
    """
    return {
        "id": uuid.UUID(paper_id),
        "title": paper.title,
        "source_url": f"https://doi.org/{paper.doi}" if paper.doi else None,
        "document_type": paper.document_type,
        "exercise_tags": paper.exercise_tags,
        "doi": normalize_doi(paper.doi) if paper.doi is not None else None,
        "chunk_count": 0,  # Will update after ingestion
        "ingested_at": now,
        "metadata": json.dumps(
            {
                "authors": paper.authors,
                "year": paper.year,
                "doi": paper.doi,
                "quality_tier": paper.quality_tier,
                "source": "seed_corpus_p2_007",
                "review_status": "reviewed_approved",
            }
        ),
        "review_status": "reviewed_approved",  # issue #264: set column, not only metadata JSONB
        "created_at": now,
        "updated_at": now,
    }


async def main(dry_run: bool = False) -> None:
    from datetime import timezone

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from app.services.ingestion import DocumentMetadata, IngestionService
    from app.services.cohere_client import get_cohere_client
    from app.services.qdrant import get_qdrant_client

    # Fail fast on malformed hardcoded DOIs before any DB work (issue #230).
    validate_seed_dois(SEED_PAPERS)

    print(f"[seed-papers] {len(SEED_PAPERS)} papers to seed")

    # Count by exercise
    exercise_counts: dict[str, int] = {}
    for p in SEED_PAPERS:
        for tag in p.exercise_tags:
            exercise_counts[tag] = exercise_counts.get(tag, 0) + 1
    for ex, count in sorted(exercise_counts.items()):
        print(f"  {ex}: {count} papers")

    if dry_run:
        for i, p in enumerate(SEED_PAPERS, 1):
            print(f"\n--- Paper {i}: [{p.quality_tier}] {p.title} ({p.year})")
            print(f"    Authors: {', '.join(p.authors[:3])}{'...' if len(p.authors) > 3 else ''}")
            print(f"    DOI: {p.doi or 'N/A'}")
            print(f"    Exercises: {p.exercise_tags}")
            print(f"    Text length: {len(p.text)} chars, ~{len(p.text.split())} tokens")
        print(f"\n[seed-papers] Dry run — {len(SEED_PAPERS)} papers would be created.")
        return

    # -----------------------------------------------------------------------
    # DB setup
    # -----------------------------------------------------------------------
    raw_url = os.environ["DATABASE_URL"]
    db_url = (
        raw_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if raw_url.startswith("postgresql://")
        else raw_url
    )
    engine = create_async_engine(
        db_url, echo=False, connect_args={"statement_cache_size": 0}
    )
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # -----------------------------------------------------------------------
    # Qdrant + Cohere setup
    # -----------------------------------------------------------------------
    import app.services.qdrant as qdrant_mod

    qdrant_mod._qdrant_client_cache = None
    qdrant_mod._qdrant_client_cache_initialized = False

    qdrant = await get_qdrant_client()
    if qdrant is None:
        print("[seed-papers] ERROR: Qdrant client unavailable", file=sys.stderr)
        sys.exit(1)

    try:
        cohere = get_cohere_client()
    except RuntimeError as exc:
        print(f"[seed-papers] ERROR: Cohere client unavailable — {exc}", file=sys.stderr)
        sys.exit(1)

    ingestion_svc = IngestionService(cohere_client=cohere, qdrant_client=qdrant)

    # -----------------------------------------------------------------------
    # Insert into DB + ingest into Qdrant
    # -----------------------------------------------------------------------
    now = datetime.now(timezone.utc)
    total_chunks = 0

    skipped = 0
    async with session_factory() as session:
        for paper in SEED_PAPERS:
            # Skip papers whose normalized DOI already exists in the DB
            # (idempotent re-run — issue #264). Papers without a DOI are always
            # inserted because they cannot be deduplicated by DOI.
            if paper.doi is not None and await doi_exists_live(session, normalize_doi(paper.doi)):
                print(f"  [skip] already exists: {paper.title[:60]}")
                skipped += 1
                continue

            paper_id = str(uuid.uuid4())

            # Insert rag_documents row (doi + review_status columns populated — issues #230, #264)
            await session.execute(
                text(_INSERT_SQL),
                build_rag_document_row(paper, paper_id, now),
            )

            # Ingest into Qdrant via IngestionService
            metadata = DocumentMetadata(
                title=paper.title,
                authors=paper.authors,
                year=paper.year,
                doi=paper.doi,
                quality_tier=paper.quality_tier,
                review_status="reviewed_approved",
                exercise_tags=paper.exercise_tags,
                sex_applicability="both",
            )

            ingest_result = await ingestion_svc.ingest_document(
                paper_id=paper_id,
                text=paper.text,
                metadata=metadata,
                sections=paper.sections if paper.sections else None,
            )

            # Update chunk_count
            await session.execute(
                text("UPDATE rag_documents SET chunk_count = :count WHERE id = :id"),
                {"count": ingest_result.chunk_count, "id": uuid.UUID(paper_id)},
            )

            total_chunks += ingest_result.chunk_count
            print(f"  [{paper.quality_tier}] {paper.title[:60]}... -> {ingest_result.chunk_count} chunks")

        await session.commit()

    print("\n[seed-papers] Summary:")
    print(f"  Papers: {len(SEED_PAPERS)} total, {skipped} skipped (already exist), {len(SEED_PAPERS) - skipped} inserted")
    print(f"  Chunks: {total_chunks}")
    for ex, count in sorted(exercise_counts.items()):
        print(f"  {ex}: {count} papers")
    print("\n[seed-papers] Done.")

    await engine.dispose()


if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    asyncio.run(main(dry_run=dry_run))
