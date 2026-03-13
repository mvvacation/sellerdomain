"""Tests for export module."""

import csv
import json

import pytest

from core.exporter import export, export_csv, export_json


def _make_lead(**overrides):
    base = {
        "name": "TestCo",
        "website": "https://testco.com",
        "website_domain": "testco.com",
        "relevance_score": 75,
        "buyer_type": "brand_match",
        "emails": ["info@testco.com"],
        "phone": "+1-555-123-4567",
        "social": {"linkedin": "https://linkedin.com/company/testco"},
        "technologies": ["React", "Node.js"],
        "description": "Test company",
        "snippet": "",
        "relevance_reasons": ["Strong brand fit"],
        "score_breakdown": {"brand_fit": 20, "content_match": 10},
        "matched_queries": ["test company"],
    }
    base.update(overrides)
    return base


def _make_analysis():
    return {
        "domain": "test.com",
        "name": "test",
        "tld": "com",
        "keywords": ["test"],
        "industries": ["technology"],
    }


class TestExportCSV:
    def test_creates_csv_file(self, tmp_path):
        path = tmp_path / "leads.csv"
        leads = [_make_lead(), _make_lead(name="OtherCo")]
        result = export_csv(leads, str(path))
        assert path.exists()
        assert result == str(path)

    def test_csv_has_header_and_rows(self, tmp_path):
        path = tmp_path / "leads.csv"
        leads = [_make_lead()]
        export_csv(leads, str(path))

        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert len(rows) == 1
        assert rows[0]["name"] == "TestCo"
        assert rows[0]["relevance_score"] == "75"

    def test_csv_phone_field_not_empty(self, tmp_path):
        """Regression test: phone field was using 'phones' key instead of 'phone'."""
        path = tmp_path / "leads.csv"
        leads = [_make_lead(phone="+1-555-123-4567")]
        export_csv(leads, str(path))

        with open(path, encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
        assert rows[0]["phone"] == "+1-555-123-4567"


class TestExportJSON:
    def test_creates_json_file(self, tmp_path):
        path = tmp_path / "leads.json"
        leads = [_make_lead()]
        result = export_json(leads, str(path), _make_analysis())
        assert path.exists()
        assert result == str(path)

    def test_json_structure(self, tmp_path):
        path = tmp_path / "leads.json"
        leads = [_make_lead()]
        export_json(leads, str(path), _make_analysis())

        with open(path, encoding="utf-8") as f:
            data = json.load(f)
        assert "domain_analysis" in data
        assert "leads" in data
        assert "total_leads" in data
        assert data["total_leads"] == 1


class TestExportAutoDetect:
    def test_csv_detection(self, tmp_path):
        path = tmp_path / "test.csv"
        export([_make_lead()], str(path))
        assert path.exists()

    def test_json_detection(self, tmp_path):
        path = tmp_path / "test.json"
        export([_make_lead()], str(path))
        assert path.exists()

    def test_unknown_extension_defaults_to_csv(self, tmp_path):
        path = tmp_path / "test.txt"
        export([_make_lead()], str(path))
        assert path.exists()
