from app.models.coaching_result import CoachingResult


def test_coaching_result_has_eval_scores_json_column():
    columns = {c.name for c in CoachingResult.__table__.columns}
    assert "eval_scores_json" in columns
