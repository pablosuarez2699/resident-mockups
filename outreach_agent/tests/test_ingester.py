import config
from pipeline.ingester import ingest, lead_from_flags


def _write_csv(tmp_path, text):
    p = tmp_path / "leads.csv"
    p.write_text(text)
    return str(p)


def test_ingest_maps_headers_and_splits_name(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LEAD_SOURCE", "csv")
    path = _write_csv(tmp_path,
        "Company Name,Decision Maker,Title,Email,Carrier (Est.),Relationship\n"
        "Acme Co,Sarah Chen,VP Operations,sarah@acme.ca,FedEx,current\n")
    leads = ingest(path)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.company_name == "Acme Co"
    assert lead.first_name == "Sarah" and lead.last_name == "Chen"
    assert lead.title == "VP Operations"
    assert lead.email == "sarah@acme.ca"
    assert lead.current_carrier_estimated == "FedEx"
    assert lead.relationship_status == "current"


def test_missing_email_row_is_kept(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LEAD_SOURCE", "csv")
    path = _write_csv(tmp_path,
        "Company Name,Contact,Email\n"
        "NoEmail Inc,Pat Lee,\n")
    leads = ingest(path)
    assert len(leads) == 1
    assert leads[0].email == ""
    assert leads[0].full_name == "Pat Lee"


def test_relationship_inferred_from_lead_type(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LEAD_SOURCE", "csv")
    path = _write_csv(tmp_path,
        "Company Name,Lead Type\n"
        "Old Client,REACTIVATION\n"
        "Fresh Co,NEW\n")
    leads = ingest(path)
    by_company = {lead.company_name: lead for lead in leads}
    assert by_company["Old Client"].relationship_status == "lapsed"
    assert by_company["Fresh Co"].relationship_status == "prospect"


def test_blank_rows_skipped(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "LEAD_SOURCE", "csv")
    path = _write_csv(tmp_path, "Company Name,Contact\nReal Co,Sam\n,\n")
    assert len(ingest(path)) == 1


def test_placeholder_values_treated_as_empty(tmp_path, monkeypatch):
    # The prospecting report uses "—" for unknown contact and "Find via Sales Nav →" for title
    monkeypatch.setattr(config, "LEAD_SOURCE", "csv")
    path = _write_csv(tmp_path,
        "Company Name,Decision Maker,Title,Email\n"
        "TGE Industrial,—,Find via Sales Nav →,\n")
    leads = ingest(path)
    assert len(leads) == 1
    lead = leads[0]
    assert lead.first_name == "" and lead.last_name == ""
    assert lead.title == ""
    assert lead.greeting_name == "there"   # clean fallback, not "—"


def test_bad_path_returns_empty(monkeypatch):
    monkeypatch.setattr(config, "LEAD_SOURCE", "csv")
    assert ingest("/nonexistent/file.csv") == []


def test_lead_from_flags():
    lead = lead_from_flags(company="Acme", name="Sarah Chen", email="s@acme.ca",
                           relationship="lapsed", carrier="UPS")
    assert lead.company_name == "Acme"
    assert lead.first_name == "Sarah" and lead.last_name == "Chen"
    assert lead.relationship_status == "lapsed"
