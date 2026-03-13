"""Tests for outreach email generation."""

from core.outreach import generate_all_templates, generate_outreach_email


def _make_analysis(**overrides):
    base = {
        "domain": "healthtrack.com",
        "name": "healthtrack",
        "tld": "com",
        "keywords": ["health", "track"],
        "industries": ["health"],
        "estimated_value_low": 5000,
        "estimated_value_high": 15000,
        "domain_age_years": 5,
        "history": {},
        "social_handles": {},
        "market_comp": {},
        "brandability": {"score": 75, "grade": "A"},
        "niche_context": "",
        "geo_targets": [],
    }
    base.update(overrides)
    return base


def _make_lead(**overrides):
    base = {
        "name": "HealthCo",
        "website": "https://healthco.io",
        "website_domain": "healthco.io",
        "buyer_type": "brand_match",
        "relevance_score": 65,
        "relevance_reasons": ["Keywords match company focus"],
        "emails": ["info@healthco.io"],
        "phone": "",
        "social": {},
        "technologies": [],
        "description": "Digital health platform",
        "location": "",
    }
    base.update(overrides)
    return base


class TestGenerateOutreachEmail:
    def test_returns_subject_and_body(self):
        email = generate_outreach_email(_make_lead(), _make_analysis())
        assert "subject" in email
        assert "body" in email
        assert len(email["subject"]) > 0
        assert len(email["body"]) > 0

    def test_includes_domain_name(self):
        email = generate_outreach_email(_make_lead(), _make_analysis())
        assert "healthtrack.com" in email["subject"] or "healthtrack.com" in email["body"]

    def test_includes_company_name(self):
        email = generate_outreach_email(_make_lead(), _make_analysis())
        assert "HealthCo" in email["body"]

    def test_auto_selects_similar_domain_template(self):
        lead = _make_lead(buyer_type="similar_domain", is_similar_domain=True)
        email = generate_outreach_email(lead, _make_analysis())
        assert "consolidate" in email["subject"].lower() or "brand" in email["subject"].lower()

    def test_auto_selects_startup_template(self):
        lead = _make_lead(buyer_type="funded_startup")
        email = generate_outreach_email(lead, _make_analysis())
        assert "momentum" in email["body"].lower() or "scale" in email["body"].lower()

    def test_auto_selects_premium_template(self):
        lead = _make_lead(buyer_type="brand_match", relevance_score=75)
        email = generate_outreach_email(lead, _make_analysis())
        assert "premium" in email["body"].lower() or "strategic" in email["body"].lower()

    def test_explicit_template_type(self):
        email = generate_outreach_email(_make_lead(), _make_analysis(), template_type="upgrade")
        assert "upgrade" in email["subject"].lower() or "upgrade" in email["body"].lower()


class TestGenerateAllTemplates:
    def test_returns_all_five_types(self):
        templates = generate_all_templates(_make_lead(), _make_analysis())
        expected = {"standard", "premium", "startup", "similar_domain", "upgrade"}
        assert set(templates.keys()) == expected

    def test_all_templates_have_subject_and_body(self):
        templates = generate_all_templates(_make_lead(), _make_analysis())
        for name, email in templates.items():
            assert "subject" in email, f"Missing subject in {name}"
            assert "body" in email, f"Missing body in {name}"
            assert len(email["subject"]) > 0
            assert len(email["body"]) > 0

    def test_templates_are_distinct(self):
        templates = generate_all_templates(_make_lead(), _make_analysis())
        subjects = [t["subject"] for t in templates.values()]
        # At least most templates should have different subjects
        assert len(set(subjects)) >= 3
