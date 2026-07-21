from app.ai.prompts import build_user_message
from app.daily_questions import _contains_disallowed_material


def test_daily_prompt_allows_debate_but_excludes_sexual_content():
    prompt = build_user_message(
        task="daily_poll",
        text="Explore a controversial question",
        target_locale="en",
        exclude_questions=["Old question"],
    )
    assert "controversial" in prompt
    assert "pornography" in prompt
    assert "Old question" in prompt


def test_daily_question_safety_filter_rejects_disallowed_material():
    assert _contains_disallowed_material("Would porn be legal?")
    assert _contains_disallowed_material("色情内容")
    assert not _contains_disallowed_material("Should cities ban cars downtown?")
