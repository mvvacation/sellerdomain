"""Tests for lead scoring algorithm."""

import pytest

from core.lead_scorer import LeadScorer


def _make_analysis(**overrides):
    base = {
        "domain": "healthtrack.com",
        "name": "healthtrack",
        "tld": "com",
        "keywords": ["health", "track"],
        "industries": ["health", "technology"],
        "geo_targets": [],
        "niche_context": "",
    }
    base.update(overrides)
    return base


def _make_lead(**overrides):
    base = {
        "name": "HealthCo",
        "website": "https://healthco.io",
        "website_domain": "healthco.io",
        "title": "HealthCo - Digital Health Platform",
        "snippet": "Health tracking platform for patients",
        "description": "A digital health tracking solution",
        "matched_queries": ["health track company"],
        "emails": [],
        "phone": "",
        "social": {},
        "location": "",
        "employee_count": "",
        "technologies": [],
    }
    base.update(overrides)
    return base


class TestLeadScorer:
    def test_score_range(self):
        scorer = LeadScorer(_make_analysis())
        leads = [_make_lead()]
        scored = scorer.score_and_rank(leads)
        assert 0 <= scored[0]["relevance_score"] <= 100

    def test_scored_leads_sorted(self):
        scorer = LeadScorer(_make_analysis())
        leads = [
            _make_lead(name="Low Match", website_domain="random.xyz", description="unrelated"),
            _make_lead(name="HealthTrack", website_domain="healthtrack.io"),
        ]
        scored = scorer.score_and_rank(leads)
        assert scored[0]["relevance_score"] >= scored[1]["relevance_score"]

    def test_exact_match_high_brand_fit(self):
        scorer = LeadScorer(_make_analysis())
        lead = _make_lead(name="HealthTrack", website_domain="healthtrack.io")
        breakdown = scorer._score_breakdown(lead)
        assert breakdown["brand_fit"] >= 15

    def test_domain_gap_tld_upgrade(self):
        scorer = LeadScorer(_make_analysis(tld="com"))
        lead = _make_lead(website_domain="healthtrack.xyz")
        breakdown = scorer._score_breakdown(lead)
        assert breakdown["domain_gap"] >= 2

    def test_similar_domain_high_gap(self):
        scorer = LeadScorer(_make_analysis())
        lead = _make_lead(is_similar_domain=True)
        breakdown = scorer._score_breakdown(lead)
        assert breakdown["domain_gap"] >= 10

    def test_discovery_depth_scales(self):
        scorer = LeadScorer(_make_analysis())
        single_q = _make_lead(matched_queries=["q1"])
        multi_q = _make_lead(matched_queries=["q1", "q2", "q3", "q4"])
        assert scorer._discovery_depth(multi_q) > scorer._discovery_depth(single_q)

    def test_actionability_with_email(self):
        scorer = LeadScorer(_make_analysis())
        with_email = _make_lead(emails=["hi@healthco.io"])
        without_email = _make_lead(emails=[])
        assert scorer._actionability(with_email) > scorer._actionability(without_email)

    def test_actionability_matching_domain_email(self):
        scorer = LeadScorer(_make_analysis())
        lead = _make_lead(emails=["hi@healthco.io"], website_domain="healthco.io")
        pts = scorer._actionability(lead)
        assert pts >= 6  # 4 for email + 2 for matching domain

    def test_buyer_signals_funding(self):
        scorer = LeadScorer(_make_analysis())
        funded = _make_lead(description="Just raised Series A funding of $10M")
        unfunded = _make_lead(description="A small local business")
        assert scorer._buyer_signals(funded) > scorer._buyer_signals(unfunded)

    def test_buyer_signals_rebrand(self):
        scorer = LeadScorer(_make_analysis())
        lead = _make_lead(description="The company is rebranding and looking for domain acquisition")
        pts = scorer._buyer_signals(lead)
        assert pts >= 5

    def test_content_match_keywords(self):
        scorer = LeadScorer(_make_analysis(keywords=["health", "track"]))
        good = _make_lead(
            description="health tracking platform for fitness",
            title="HealthTrack Platform",
            snippet="",
        )
        bad = _make_lead(
            description="selling shoes online",
            title="Shoe Store",
            snippet="",
            name="ShoeStore",
            website_domain="shoestore.xyz",
        )
        assert scorer._content_match(good) >= scorer._content_match(bad)

    def test_score_breakdown_has_all_categories(self):
        scorer = LeadScorer(_make_analysis())
        lead = _make_lead()
        breakdown = scorer._score_breakdown(lead)
        expected_keys = ["brand_fit", "content_match", "domain_gap",
                         "discovery_depth", "actionability", "buyer_signals"]
        for key in expected_keys:
            assert key in breakdown

    def test_buyer_type_similar_domain(self):
        scorer = LeadScorer(_make_analysis())
        lead = _make_lead(is_similar_domain=True)
        breakdown = scorer._score_breakdown(lead)
        lead["relevance_score"] = sum(breakdown.values())
        buyer_type = scorer._classify_buyer(lead, breakdown)
        assert buyer_type == "similar_domain"

    def test_relevance_reasons_not_empty(self):
        scorer = LeadScorer(_make_analysis())
        leads = scorer.score_and_rank([_make_lead()])
        assert len(leads[0]["relevance_reasons"]) > 0


class TestGeoScoring:
    def test_geo_match_boosts_content(self):
        scorer = LeadScorer(_make_analysis(geo_targets=["San Francisco"]))
        local = _make_lead(location="San Francisco, CA", description="health startup")
        remote = _make_lead(location="London, UK", description="health startup")
        assert scorer._content_match(local) > scorer._content_match(remote)
