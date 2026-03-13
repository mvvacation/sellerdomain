"""Tests for shared HTTP utilities."""

from core.http_utils import USER_AGENT, create_session


class TestCreateSession:
    def test_returns_session(self):
        session = create_session()
        assert session is not None
        session.close()

    def test_user_agent_set(self):
        session = create_session()
        assert "DomainSeller" in session.headers.get("User-Agent", "")
        session.close()

    def test_custom_user_agent(self):
        session = create_session(user_agent="Custom/1.0")
        assert session.headers["User-Agent"] == "Custom/1.0"
        session.close()


class TestUserAgent:
    def test_identifies_as_domainseller(self):
        assert "DomainSeller" in USER_AGENT

    def test_includes_version(self):
        assert "2.1" in USER_AGENT
