import pytest

from models.mode_config import resolve_mode, OUTREACH_MODES


def test_canonical_names_resolve():
    assert resolve_mode("no_answer").name == "no_answer"
    assert resolve_mode("follow_up").name == "follow_up"


def test_aliases_resolve():
    for kw in ["no-answer", "intro", "voicemail", "VM", "Missed"]:
        assert resolve_mode(kw).name == "no_answer"
    for kw in ["follow-up", "followup", "post-call", "proposal", "recap"]:
        assert resolve_mode(kw).name == "follow_up"


def test_unknown_keyword_raises_with_help():
    with pytest.raises(ValueError) as exc:
        resolve_mode("bogus")
    msg = str(exc.value)
    assert "bogus" in msg
    assert "no_answer" in msg and "follow_up" in msg


def test_every_mode_has_prompt_and_template():
    for mode in OUTREACH_MODES.values():
        assert mode.prompt_file and mode.template_file and mode.subject_template
