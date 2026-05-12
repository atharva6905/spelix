# Spelix Private Beta Terms

**Last updated: 2026-05-12**

## 1. Beta status and purpose

Spelix is an invite-only private beta. The service analyses your squat, bench, or deadlift video and generates structured coaching feedback grounded in peer-reviewed biomechanics literature. All feedback is for educational and performance purposes only. Spelix is not a medical device and is not a substitute for advice from a qualified coach, physiotherapist, or medical professional.

## 2. Eligibility

You must be at least 18 years old to use Spelix. Access is by invitation only. Each person may hold one account. You are responsible for keeping your login credentials secure.

## 3. What Spelix does

When you upload a barbell exercise video, Spelix runs a computer-vision pipeline that extracts body-pose landmarks (joint coordinates) from each frame. An AI model then analyses those landmarks alongside peer-reviewed biomechanics research to produce structured coaching feedback. The feedback covers four dimensions: Movement Quality, Technique, Path and Balance, and Control. An expert reviewer may also review flagged analyses.

This feedback is for educational and performance purposes only. It is not a substitute for advice from a qualified coach, physiotherapist, or medical professional.

## 4. How your data is processed

Spelix uses automated decision-making to generate your coaching feedback, as described below (GDPR Article 22 disclosure):

- **Pose extraction.** A computer-vision model (MediaPipe BlazePose) detects body-joint positions in each video frame and converts them into numeric coordinates. No facial recognition is performed.
- **Rep detection and scoring.** Algorithms identify individual repetitions, calculate joint angles and bar path, and produce scores across four dimensions.
- **AI coaching.** A large language model receives your scores, joint-angle data, and relevant biomechanics literature, then generates written feedback. The model does not receive your raw video.
- **Expert review.** Analyses that are flagged (for example, due to low confidence or unusual patterns) may be reviewed by a qualified human reviewer before coaching is finalised.

You have the right to request human review of any automated decision. Contact atharva6905@gmail.com.

The legal basis for processing your exercise data is your explicit consent under GDPR Article 6(1)(b) (performance of the service you requested) and Article 9(2)(a) (explicit consent for special-category health-related data). You provide this consent through the in-app consent flow before your first analysis.

## 5. Consent model

Before you can submit an analysis, Spelix asks for your explicit consent in three tiers:

1. **Analytics** (required) — anonymised usage data such as page views and feature usage. No personally identifiable information is collected.
2. **Health data processing** (required) — your video is processed by computer-vision and AI models to extract joint angles, rep timing, and movement-quality metrics. This data is treated as special-category health data under GDPR Article 9.
3. **Coach Brain contribution** (optional) — your anonymised movement patterns may be used to improve coaching quality for all users. Data is never shared individually and is always grouped with at least 20 other users before any pattern is extracted. You can withdraw this consent at any time without affecting the service.

Consent for health data processing is separate from these terms, as required by GDPR Article 7. You grant or withdraw each tier independently through your in-app consent settings.

## 6. Data retention

| Data type | Retention period |
|-----------|-----------------|
| Raw video file | Deleted immediately after pose extraction is complete |
| Annotated video and PDF report | 7 days, then automatically deleted |
| Analysis records (scores, metrics, coaching text) | 24 months from creation, or until you delete your account, whichever comes first |
| Account profile information | Until you delete your account |
| Anonymised aggregates (Coach Brain) | Indefinite; cannot be traced back to any individual |

## 7. Your rights

Under GDPR, you have the right to:

- **Access** your data — view all your analyses, scores, and profile information in the app at any time.
- **Export** your data — download your analysis data from your profile.
- **Delete** your account and all associated data from your profile settings.
- **Withdraw consent** — revoke any consent tier at any time through the in-app consent settings. Withdrawing health-data-processing consent will prevent you from submitting new analyses but will not affect previously completed ones.
- **Request human review** of any automated coaching decision.
- **Lodge a complaint** with your local data-protection supervisory authority.

To exercise any right outside the app, email atharva6905@gmail.com.

A Data Protection Impact Assessment (DPIA) has been completed for Spelix in accordance with GDPR Article 35.

## 8. Coach Brain and anonymisation

The Coach Brain is an internal learning layer that identifies common movement patterns across users to improve coaching quality. It operates under strict anonymisation rules:

- Participation is opt-in only (Tier 3 consent above).
- Data is grouped into categorical bins (such as experience level or stance width category), never precise measurements.
- No pattern is surfaced unless it is derived from at least 20 distinct users (k-anonymity threshold).
- Individual analyses are never stored in the Coach Brain. Only aggregated, de-identified patterns are retained.
- You can withdraw your Coach Brain consent at any time. Previously contributed anonymised data that has already been aggregated cannot be individually removed, but no further data will be contributed from your account.

## 9. Service availability and limitations

Spelix is a beta product. You should expect:

- Occasional downtime for maintenance or updates, without advance notice.
- Features may be added, changed, or removed at any time.
- There is no service-level agreement (SLA) or uptime guarantee.
- Spelix may revoke beta access at its discretion.
- Coaching feedback quality may vary. Always apply your own judgement and consult a qualified professional for important training decisions.

## 10. Changes to these terms

We may update these terms from time to time. When we do, we will update the "Last updated" date at the top of this page and notify you by email. Your continued use of Spelix after a change constitutes acceptance of the updated terms. If you do not agree with a change, you may delete your account at any time.

## Contact

For questions, data requests, or feedback: **atharva6905@gmail.com**
