"""CoachingService — Phase 0/1/2 LLM coaching pipeline.

Calls Claude Sonnet 4.6 via the instructor library to produce a structured
CoachingOutput validated by Pydantic v2.

Requirements: FR-RESL-03, Appendix D (B-023), FR-AICP-08

Error handling (per Appendix D.2):
    - 429 / 529 (rate limit / overload): exponential backoff 1s → 2s → 4s,
      max 3 retries. Raises the final exception if all retries exhaust.
    - 401 (auth error): fail immediately, CRITICAL log, no retries.
    - 400 (bad request): fail immediately, log full context.
    - Network timeout: 60s total; on timeout treat as 529 (apply backoff).

Notes:
    - Never use "injury risk" or "injury prevention" in prompts or output.
    - This service is called from the ARQ worker (wired in B-024).
    - Never call the real Anthropic API in tests — always mock.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any

import anthropic
import instructor

from app.config import ThresholdConfig
from app.cv.confidence import confidence_label
from app.schemas.coaching import CoachingOutput
from app.schemas.rag import CitationBlock, RetrievedContext

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants (Appendix D)
# ---------------------------------------------------------------------------

MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0.3
MAX_TOKENS = 2048
NETWORK_TIMEOUT_S = 60.0

MANDATORY_DISCLAIMER = (
    "This feedback is for educational purposes only and is not a substitute "
    "for in-person coaching or medical advice."
)

# Retry schedule for 429 / 529 / timeout (Appendix D.2)
_BACKOFF_DELAYS: tuple[float, ...] = (1.0, 2.0, 4.0)

# ---------------------------------------------------------------------------
# Prompt builders
# ---------------------------------------------------------------------------


def _build_system_prompt() -> str:
    """Return the stable system prompt (candidate for prompt caching in Phase 1).

    Priority enforcement per FR-AICP-04:
      1. Movement Quality — breakdown patterns and motor control
      2. Technique — positional deviations from optimal mechanics
      3. Path & Balance — bar path, weight distribution, lateral drift
      4. Control — tempo, consistency, fatigue effects
    """
    return (
        "You are an expert barbell strength coach providing objective, "
        "evidence-based technique feedback. You are NOT a medical professional. "
        "All feedback is for educational and performance purposes only.\n\n"
        "This analysis evaluates Movement Quality, Technique, Path & Balance, "
        "and Control — grounded in peer-reviewed biomechanics research.\n\n"
        "PRIORITY ORDER — always address dimensions in this exact sequence:\n"
        "  1. Movement Quality: identify form breakdown patterns and motor control "
        "deviations across the full range of motion.\n"
        "  2. Technique: identify positional deviations from optimal joint mechanics "
        "(e.g. knee tracking, spinal alignment, elbow position).\n"
        "  3. Path & Balance: assess bar path deviation, lateral drift, and "
        "centre-of-mass balance across the base of support.\n"
        "  4. Control: evaluate tempo consistency, rep-to-rep variability, and "
        "any fatigue-related form degradation.\n\n"
        "For each identified deviation:\n"
        "  - Reference the exact rep number, joint, and movement phase.\n"
        "  - Provide a 'Recommended Cues' list with specific verbal or tactile cues "
        "the coach can use with the lifter.\n"
        "  - When referencing research, include a citation (title, authors, year, "
        "and DOI if available).\n\n"
        "Tone: direct, supportive, non-judgmental. Be specific — never give generic "
        "advice.\n\n"
        "PROHIBITED LANGUAGE — never use any of these phrases:\n"
        "  - phrases combining the word 'injury' with 'risk' or 'prevention'\n"
        "  - 'prevent injury', 'diagnose', 'treat', 'medical', 'clinical'\n"
        "USE INSTEAD:\n"
        "  - 'Movement Quality', 'movement pattern', 'form breakdown', "
        "'technique deviation', 'loading concern'\n\n"
        f'End every response with the mandatory disclaimer: "{MANDATORY_DISCLAIMER}"'
    )


def build_citation_blocks(contexts: list[RetrievedContext]) -> list[CitationBlock]:
    """Convert retrieved contexts to numbered CitationBlock list for the prompt.

    Assigns 1-based index values matching the [N] markers embedded in the
    prompt's Retrieved Evidence section.  The caller passes this list alongside
    the prompt so downstream code can cross-reference LLM output citations.

    Parameters
    ----------
    contexts:
        Ordered list of RetrievedContext objects (already reranked).

    Returns
    -------
    list[CitationBlock]
        One CitationBlock per context, index starting at 1.
    """
    blocks: list[CitationBlock] = []
    from app.schemas.rag import ChunkPayload

    for i, ctx in enumerate(contexts, start=1):
        chunk = ctx.chunk
        # Truncate excerpt to 300 chars to keep prompts manageable
        excerpt = chunk.text[:300].strip()
        # ChunkPayload carries full citation metadata (authors/doi); the slim
        # Chunk model used by distillation test stubs does not. Coaching
        # always produces ChunkPayload from the retrieval pipeline — this
        # isinstance narrow keeps pyright happy across the union widening
        # introduced in ADR-DISTILL-04.
        authors = chunk.authors if isinstance(chunk, ChunkPayload) else []
        doi = chunk.doi if isinstance(chunk, ChunkPayload) else None
        blocks.append(
            CitationBlock(
                index=i,
                title=chunk.title,
                authors=authors,
                year=chunk.year,
                doi=doi,
                chunk_text_excerpt=excerpt,
            )
        )
    return blocks


def _build_user_prompt(
    exercise_type: str,
    exercise_variant: str,
    rep_metrics: list[dict[str, Any]],
    confidence_score: float,
    thresholds: ThresholdConfig,
    body_stats: dict[str, Any] | None = None,
    keyframe_analysis_text: str | None = None,
    retrieved_contexts: list[RetrievedContext] | None = None,
    retrieval_source: str | None = None,
) -> str:
    """Build the per-analysis user turn (fresh context, not cached).

    Parameters
    ----------
    exercise_type:
        One of "squat", "bench", "deadlift".
    exercise_variant:
        Exercise-specific variant string (e.g. "high_bar", "conventional").
    rep_metrics:
        List of per-rep metric dicts from the CV pipeline.
    confidence_score:
        Mean landmark visibility / Tier 5 score (0–1).
    thresholds:
        Loaded ThresholdConfig instance.
    body_stats:
        Optional athlete profile dict (e.g. height, weight, limb ratios).
        When None, general population coaching standards are applied.
    keyframe_analysis_text:
        Optional GPT-4o keyframe analysis text (Phase 1 visual analysis).
        When provided, prepended as a "Visual Analysis" section.
    retrieved_contexts:
        Optional list of reranked RetrievedContext objects from the RAG
        pipeline (Phase 2, FR-AICP-08). When provided and non-empty, a
        numbered "Retrieved Evidence" section is prepended and cite-then-
        generate instructions are appended. When None or empty, the prompt
        is identical to the Phase 1 format.
    """
    rep_count = len(rep_metrics)
    confidence_label_str = confidence_label(confidence_score)

    # Summarise rep metrics as compact JSON for the model
    metrics_summary = json.dumps(rep_metrics, indent=2)

    # Pull relevant thresholds for the exercise
    try:
        exercise_thresholds = thresholds.all_for_exercise(exercise_type)
        threshold_summary = json.dumps(exercise_thresholds, indent=2)
    except KeyError:
        threshold_summary = "{}"

    lines: list[str] = [
        f"Exercise: {exercise_type} — {exercise_variant}",
        f"Analysis results: {rep_count} reps detected. Confidence: {confidence_label_str}.",
    ]

    if confidence_label_str in ("Low", "Very Low"):
        lines.append(
            "Note: analysis confidence was low for this session — results should "
            "be interpreted with caution."
        )

    lines.append("")

    # Athlete profile section (FR-AICP-05)
    if body_stats is not None:
        athlete_profile_json = json.dumps(body_stats, indent=2)
        lines += [
            "Athlete Profile:",
            athlete_profile_json,
            "",
        ]
    else:
        lines += [
            "No athlete profile on file — apply general population coaching standards.",
            "",
        ]

    # Visual analysis section from GPT-4o keyframe analysis (Phase 1)
    if keyframe_analysis_text is not None:
        lines += [
            "Visual Analysis (keyframe):",
            keyframe_analysis_text,
            "",
        ]

    # Retrieved Evidence section (Phase 2 — FR-AICP-08 cite-then-generate)
    if retrieved_contexts:
        citation_blocks = build_citation_blocks(retrieved_contexts)
        lines.append("Retrieved Evidence:")
        for block in citation_blocks:
            authors_str = ", ".join(block.authors) if block.authors else "Unknown"
            year_str = str(block.year) if block.year is not None else "n.d."
            doi_str = f" DOI: {block.doi}" if block.doi else ""
            # P2-026 (FR-BRAIN-04): tag each item with source label when
            # retrieval_source is provided. Labels are prompt-internal markers
            # consumed during generation and stripped before output.
            source_label = ""
            if retrieval_source is not None:
                ctx = retrieved_contexts[block.index - 1]
                if ctx.collection == "coach_brain":
                    source_label = "[COACHING] "
                else:
                    source_label = "[RESEARCH] "
            lines.append(
                f"{source_label}[{block.index}] {block.title} ({authors_str}, {year_str}).{doi_str}"
            )
            lines.append(f'    "{block.chunk_text_excerpt}" (relevance: {retrieved_contexts[block.index - 1].score:.2f})')
        lines += [
            "",
            "When referencing evidence from the Retrieved Evidence section above, cite by",
            "number (e.g., [1], [2]). Only cite evidence that directly supports your point.",
            "Do not fabricate citations.",
            "",
        ]

    lines += [
        f"Per-rep metrics:\n{metrics_summary}",
        "",
        f"Relevant thresholds (reference values for this exercise):\n{threshold_summary}",
        "",
        "Provide structured feedback in the priority order defined in the system prompt:",
        "1. Movement Quality  2. Technique  3. Path & Balance  4. Control",
        "Include: SUMMARY (2 sentences), STRENGTHS (2–3 bullets), ISSUES (rep#, joint, "
        "description, severity: High/Medium/Low), CORRECTION PLAN (3–5 actionable cues), "
        "RECOMMENDED CUES (verbal/tactile cues for the lifter), "
        "CITATIONS (if referencing research), DISCLAIMER (mandatory).",
    ]

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Retry helpers
# ---------------------------------------------------------------------------


def _is_retryable(exc: Exception) -> bool:
    """Return True if the exception should trigger exponential backoff."""
    if isinstance(exc, anthropic.RateLimitError):
        return True
    if isinstance(exc, anthropic.APIStatusError):
        # 529 = overload
        return exc.status_code == 529
    if isinstance(exc, (TimeoutError, anthropic.APITimeoutError)):
        return True
    return False


def _is_auth_error(exc: Exception) -> bool:
    """Return True if the exception is a non-retryable auth failure."""
    return isinstance(exc, anthropic.AuthenticationError)


# ---------------------------------------------------------------------------
# CoachingService
# ---------------------------------------------------------------------------


class CoachingService:
    """Phase 0/1/2 coaching service: structured LLM call via instructor.

    Parameters
    ----------
    anthropic_client:
        An ``anthropic.AsyncAnthropic`` instance (or sync ``anthropic.Anthropic``).
        Pass ``None`` only when the caller guarantees the instructor client will
        never be invoked (e.g., pure unit-test mocking of the entire class).
    model:
        Anthropic model ID. Defaults to ``claude-sonnet-4-6``.
    langfuse_client:
        Optional ``langfuse.Langfuse`` instance for observability (P2-034).
        Pass ``None`` (default) to disable Langfuse tracing — all pipeline
        behaviour is unchanged. All Langfuse calls are best-effort and wrapped
        in try/except so observability failures never break coaching.
    """

    def __init__(
        self,
        anthropic_client: anthropic.AsyncAnthropic | anthropic.Anthropic | None,
        model: str = MODEL,
        langfuse_client: Any | None = None,
    ) -> None:
        self._model = model
        self._raw_client = anthropic_client
        self._langfuse_client = langfuse_client
        if anthropic_client is None:
            # Defer instructor wrapping — will raise on use if not mocked
            self._instructor_client: Any = None
        else:
            self._instructor_client = instructor.from_anthropic(anthropic_client)

    async def generate_coaching(
        self,
        *,
        exercise_type: str,
        exercise_variant: str,
        rep_metrics: list[dict[str, Any]],
        confidence_score: float,
        thresholds: ThresholdConfig,
        body_stats: dict[str, Any] | None = None,
        keyframe_analysis_text: str | None = None,
        retrieved_contexts: list[RetrievedContext] | None = None,
        retrieval_source: str | None = None,
    ) -> CoachingOutput:
        """Call Claude and return a validated CoachingOutput.

        Parameters
        ----------
        exercise_type:
            One of "squat", "bench", "deadlift".
        exercise_variant:
            Exercise-specific variant string (e.g. "high_bar", "conventional").
        rep_metrics:
            List of per-rep metric dicts extracted by the CV pipeline.
        confidence_score:
            Mean landmark visibility / Tier 5 score across all reps (0–1).
        thresholds:
            Loaded ThresholdConfig instance.
        body_stats:
            Optional athlete profile dict (height, weight, limb ratios).
            Passed through to the user prompt. When None, general population
            coaching standards are applied.
        keyframe_analysis_text:
            Optional GPT-4o keyframe analysis text for the Visual Analysis
            section of the prompt (Phase 1). When None, section is omitted.
        retrieved_contexts:
            Optional list of reranked RetrievedContext objects from the RAG
            pipeline (Phase 2, FR-AICP-08). When provided and non-empty, the
            cite-then-generate pattern is activated in the user prompt.
            Defaults to None (Phase 0/1 behaviour unchanged).

        Returns
        -------
        CoachingOutput
            Fully validated Pydantic model ready to be stored as JSONB.

        Raises
        ------
        ValueError
            If ``anthropic_client`` was ``None`` and the instructor client is
            not available (misconfigured service with no mock).
        anthropic.AuthenticationError
            Immediately on 401 — no retries.
        anthropic.RateLimitError
            After all 3 retries are exhausted (for 429 / 529 / timeout).
        """
        if self._instructor_client is None:
            raise ValueError(
                "CoachingService was constructed with anthropic_client=None. "
                "Provide a valid client or patch the instructor client in tests."
            )

        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(
            exercise_type=exercise_type,
            exercise_variant=exercise_variant,
            rep_metrics=rep_metrics,
            confidence_score=confidence_score,
            thresholds=thresholds,
            body_stats=body_stats,
            keyframe_analysis_text=keyframe_analysis_text,
            retrieved_contexts=retrieved_contexts,
            retrieval_source=retrieval_source,
        )

        messages = [{"role": "user", "content": user_prompt}]

        last_exc: Exception | None = None

        for attempt, delay in enumerate(
            [None, *_BACKOFF_DELAYS]
        ):  # attempts: 0(initial) + 3 retries
            if delay is not None:
                await asyncio.sleep(delay)

            try:
                result: CoachingOutput = await self._instructor_client.chat.completions.create(
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    system=system_prompt,
                    messages=messages,
                    response_model=CoachingOutput,
                )
                return result

            except Exception as exc:
                if _is_auth_error(exc):
                    logger.critical(
                        "Anthropic 401 authentication error — check ANTHROPIC_API_KEY. "
                        "No retries. exercise_type=%s",
                        exercise_type,
                    )
                    raise

                if _is_retryable(exc):
                    last_exc = exc
                    attempt_num = (
                        0
                        if delay is None
                        else _BACKOFF_DELAYS.index(delay) + 1
                    )
                    logger.warning(
                        "Retryable Anthropic error (attempt %d/%d): %s",
                        attempt_num + 1,
                        len(_BACKOFF_DELAYS) + 1,
                        exc,
                    )
                    continue

                # Non-retryable, non-auth error (400, unexpected, etc.)
                logger.error(
                    "Non-retryable Anthropic error: %s. "
                    "exercise_type=%s exercise_variant=%s",
                    exc,
                    exercise_type,
                    exercise_variant,
                )
                raise

        # All retries exhausted
        assert last_exc is not None
        raise last_exc

    async def generate_coaching_streaming(
        self,
        *,
        exercise_type: str,
        exercise_variant: str,
        rep_metrics: list[dict[str, Any]],
        confidence_score: float,
        thresholds: ThresholdConfig,
        body_stats: dict[str, Any] | None = None,
        keyframe_analysis_text: str | None = None,
        retrieved_contexts: list[RetrievedContext] | None = None,
        retrieval_source: str | None = None,
        analysis_id: Any = None,
        pubsub_redis: Any = None,
    ) -> CoachingOutput:
        """Stream coaching from Claude via instructor create_partial, publish chunks to Redis.

        FR-AICP-07: Coaching output streamed via SSE.
        FR-AICP-21: Prompt caching on system prompt via Anthropic cache-control.

        Flow (D-001 — replaces stream-then-reparse pattern from ADR-021):
        1. Call instructor.create_partial with cache-control on system prompt.
        2. For each partial CoachingOutput snapshot, compute the text delta vs the
           previous snapshot and publish it to Redis channel ``coaching:{analysis_id}``.
        3. The last yielded snapshot is the fully validated CoachingOutput.
        4. After the generator exhausts, publish ``{"type": "done"}`` sentinel.
        5. Return the final validated CoachingOutput — no second LLM call.

        If pubsub_redis is None, skips Redis publishing (useful for tests).

        Parameters
        ----------
        exercise_type:
            One of "squat", "bench", "deadlift".
        exercise_variant:
            Exercise-specific variant string (e.g. "high_bar", "conventional").
        rep_metrics:
            List of per-rep metric dicts extracted by the CV pipeline.
        confidence_score:
            Mean landmark visibility / Tier 5 score across all reps (0–1).
        thresholds:
            Loaded ThresholdConfig instance.
        body_stats:
            Optional athlete profile dict (height, weight, limb ratios).
        keyframe_analysis_text:
            Optional GPT-4o keyframe analysis text (Phase 1).
        retrieved_contexts:
            Optional list of reranked RetrievedContext objects from the RAG
            pipeline (Phase 2, FR-AICP-08). When provided and non-empty, the
            cite-then-generate pattern is activated in the user prompt.
            Defaults to None (Phase 0/1 behaviour unchanged).
        analysis_id:
            Analysis UUID — used as Redis channel suffix. None → no channel.
        pubsub_redis:
            An async Redis client with a ``publish(channel, message)`` coroutine.
            None → Redis publishing is skipped entirely.
        """
        if self._instructor_client is None:
            raise ValueError(
                "CoachingService was constructed with anthropic_client=None. "
                "Provide a valid client or patch the instructor client in tests."
            )

        system_prompt = _build_system_prompt()
        user_prompt = _build_user_prompt(
            exercise_type=exercise_type,
            exercise_variant=exercise_variant,
            rep_metrics=rep_metrics,
            confidence_score=confidence_score,
            thresholds=thresholds,
            body_stats=body_stats,
            keyframe_analysis_text=keyframe_analysis_text,
            retrieved_contexts=retrieved_contexts,
            retrieval_source=retrieval_source,
        )

        channel = f"coaching:{analysis_id}" if analysis_id else None
        messages = [{"role": "user", "content": user_prompt}]

        # FR-AICP-21: cache-control on system prompt (Anthropic block format)
        system_blocks = [
            {
                "type": "text",
                "text": system_prompt,
                "cache_control": {"type": "ephemeral"},
            }
        ]

        last_exc: Exception | None = None

        for delay in [None, *_BACKOFF_DELAYS]:
            if delay is not None:
                await asyncio.sleep(delay)

            try:
                final_result: CoachingOutput | None = None
                previous_json = ""

                # instructor.create_partial is an AsyncGenerator that yields
                # progressively-complete partial CoachingOutput snapshots.
                # The last snapshot is the fully validated result.
                # No second LLM call is needed — this replaces the stream-then-reparse
                # pattern (ADR-021, D-001).
                async for partial in self._instructor_client.chat.completions.create_partial(
                    response_model=CoachingOutput,
                    messages=messages,
                    model=self._model,
                    max_tokens=MAX_TOKENS,
                    temperature=TEMPERATURE,
                    system=system_blocks,
                ):
                    final_result = partial

                    # Publish text delta to Redis for SSE endpoint.
                    # We diff the JSON representation of the partial model against
                    # the previous snapshot to produce an incremental text chunk.
                    if pubsub_redis and channel:
                        # D-049: partial snapshots from instructor.create_partial
                        # carry nested dicts (e.g. `citations: list[dict]`)
                        # against a schema declaring `list[Citation]`. Pydantic
                        # v2 fires PydanticSerializationUnexpectedValueWarning
                        # on each call, spamming worker logs. The final
                        # snapshot (returned from this method) is fully
                        # validated — suppress only on the per-partial
                        # serialization used for SSE delta publishing.
                        current_json = partial.model_dump_json(
                            exclude_none=True, warnings=False
                        )
                        # Compute the new characters added since the last snapshot
                        delta = current_json[len(previous_json):]
                        if delta:
                            await pubsub_redis.publish(
                                channel,
                                json.dumps({"type": "chunk", "text": delta}),
                            )
                        previous_json = current_json

                # Publish done sentinel after generator exhausts
                if pubsub_redis and channel:
                    await pubsub_redis.publish(
                        channel,
                        json.dumps({"type": "done"}),
                    )

                if final_result is None:
                    # Generator yielded nothing — treat as an empty response error
                    raise ValueError(
                        "instructor create_partial yielded no results for "
                        f"exercise_type={exercise_type!r}"
                    )

                return final_result

            except Exception as exc:
                if _is_auth_error(exc):
                    logger.critical(
                        "Anthropic 401 authentication error during streaming. "
                        "exercise_type=%s",
                        exercise_type,
                    )
                    raise

                if _is_retryable(exc):
                    last_exc = exc
                    logger.warning(
                        "Retryable Anthropic streaming error: %s. "
                        "exercise_type=%s",
                        exc,
                        exercise_type,
                    )
                    continue

                logger.error(
                    "Non-retryable Anthropic streaming error: %s. "
                    "exercise_type=%s exercise_variant=%s",
                    exc,
                    exercise_type,
                    exercise_variant,
                )
                raise

        assert last_exc is not None
        raise last_exc
