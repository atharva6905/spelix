"""
Integration check: pipeline Step 5 (rep detection) must pass a cfg to detect_reps.

Proves the hoist from Step 7 (confidence scoring) to above Step 5 is in place,
so Expert Reviewer threshold edits take effect for rep detection, not just
confidence scoring.
"""
from __future__ import annotations


def test_pipeline_calls_detect_reps_with_thresholdconfig_instance() -> None:
    """
    Static inspection: the call to ``detect_reps`` must pass a ``cfg``
    argument that is a ThresholdConfig instance, and cfg must be
    constructed before the rep_detection timer block.
    """
    import inspect

    from app.services import pipeline as pipeline_module

    source = inspect.getsource(pipeline_module)

    assert "detect_reps," in source, "detect_reps call site missing"

    step5_marker = 'with timer.stage("rep_detection")'
    step5_pos = source.index(step5_marker)
    cfg_construct_before_step5 = source[:step5_pos].count("ThresholdConfig()")
    assert cfg_construct_before_step5 >= 1, (
        "ThresholdConfig() must be instantiated BEFORE the rep_detection "
        "timer block (hoisted from Step 7)."
    )

    detect_reps_block = source[step5_pos : step5_pos + 500]
    assert "cfg" in detect_reps_block, (
        "detect_reps(...) call must include cfg argument"
    )
