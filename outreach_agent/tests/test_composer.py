import config
from models.lead import Lead
from models.mode_config import OUTREACH_MODES
from pipeline.composer import build_fields, render_template, compose_all


def _lead(**kw):
    base = dict(company_name="Acme Co", first_name="Sarah", last_name="Chen",
                title="VP Operations", email="sarah@acme.ca",
                current_carrier_estimated="FedEx", relationship_status="current",
                talking_points="Ships 400 parcels/week to the Prairies")
    base.update(kw)
    return Lead(**base)


def test_carrier_line_present_for_fedex():
    fields = build_fields(_lead(current_carrier_estimated="FedEx"))
    assert "Canadian carrier" in fields["carrier_line"]


def test_carrier_line_absent_for_unknown():
    fields = build_fields(_lead(current_carrier_estimated="Unknown"))
    assert fields["carrier_line"] == ""


def test_relationship_line_varies():
    cur = build_fields(_lead(relationship_status="current"))["relationship_line"]
    lap = build_fields(_lead(relationship_status="lapsed"))["relationship_line"]
    assert cur != lap and "Purolator" in cur and "Purolator" in lap


def test_render_template_no_answer():
    mode = OUTREACH_MODES["no_answer"]
    lead = _lead()
    draft = render_template(lead, mode, build_fields(lead))
    assert draft.generated_by == "template"
    assert draft.to_email == "sarah@acme.ca"
    assert "Sarah" in draft.body            # greeting
    assert config.REP_NAME in draft.body    # signature
    assert "phone" in draft.body.lower()    # phone-first framing
    assert "{" not in draft.body            # no unfilled format fields


def test_render_template_followup_uses_call_notes():
    mode = OUTREACH_MODES["follow_up"]
    lead = _lead(call_notes="wants a Q3 rate review")
    draft = render_template(lead, mode, build_fields(lead))
    assert "Q3 rate review" in draft.body
    assert draft.subject.startswith("Great speaking with you, Sarah")


def test_missing_first_name_greeting_fallback():
    mode = OUTREACH_MODES["no_answer"]
    lead = _lead(first_name="", last_name="")
    draft = render_template(lead, mode, build_fields(lead))
    assert "Hi there" in draft.body


def test_compose_all_template_path(monkeypatch):
    monkeypatch.setattr(config, "COMPOSE_MODE", "template")
    drafts = compose_all([_lead(), _lead(company_name="Beta Inc")],
                         OUTREACH_MODES["no_answer"])
    assert len(drafts) == 2
    assert all(d.generated_by == "template" for d in drafts)
