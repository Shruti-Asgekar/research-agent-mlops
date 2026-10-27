"""Simple automated checks run by GitHub Actions (no network or API key needed)."""
import pytest

import agent


def test_extract_bullets_dash():
    text = "- one\n- two\n- three\n- four"
    assert agent.extract_bullets(text) == ["one", "two", "three", "four"]


def test_extract_bullets_mixed_markers():
    text = "1. first\n2) second\n\u2022 third"
    assert agent.extract_bullets(text) == ["first", "second", "third"]


def test_extract_bullets_ignores_plain_lines():
    text = "Here is your brief:\n- only bullet\nThanks!"
    assert agent.extract_bullets(text) == ["only bullet"]


def test_format_results_contains_title_body_and_source():
    out = agent.format_results([{"title": "T", "body": "B", "href": "http://x.test"}])
    assert "[1] T" in out and "B" in out and "Source: http://x.test" in out


def test_search_web_raises_after_retries(monkeypatch):
    class FailingDDGS:
        def text(self, *args, **kwargs):
            raise Exception("boom")

    monkeypatch.setattr(agent, "DDGS", FailingDDGS)
    monkeypatch.setattr(agent.time, "sleep", lambda seconds: None)
    with pytest.raises(RuntimeError):
        agent.search_web("anything")


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    with pytest.raises(RuntimeError):
        agent.get_api_key()


def test_empty_topic_rejected():
    with pytest.raises(ValueError):
        agent.research_brief("   ")


def test_workflow_chains_both_stages(monkeypatch):
    monkeypatch.setattr(agent, "search_web", lambda topic: "raw text")
    monkeypatch.setattr(agent, "summarize", lambda topic, raw: ["a", "b", "c"])
    monkeypatch.setattr(agent, "get_model", lambda: "test-model")
    messages = []
    result = agent.research_brief("demo topic", progress=messages.append)
    assert result["bullets"] == ["a", "b", "c"]
    assert len(messages) == 2          # one progress message per stage
