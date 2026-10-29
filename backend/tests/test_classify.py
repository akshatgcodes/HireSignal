import json
from datetime import datetime

import pytest

from app import classify
from app.sources.news import Article
from tests.conftest import FakeChat


def art(title, publisher="Reuters"):
    return Article(
        f"gn:{title}", title, "https://n/x", publisher, datetime(2026, 10, 1), "google_news"
    )


@pytest.mark.parametrize(
    "title,kind,sentiment",
    [
        ("Acme lays off 300 employees", "layoffs", "bearish"),
        ("Acme to cut 1,200 jobs in restructuring", "layoffs", "bearish"),
        ("Acme raises $200M Series C", "funding", "bullish"),
        ("Acme valuation hits $10B", "funding", "bullish"),
        ("Acme opens new office in Bengaluru", "hiring", "bullish"),
        ("Acme announces hiring freeze", "hiring", "bearish"),
        ("Acme to acquire Widgets Inc", "acquisition", "neutral"),
        ("Acme sued over data breach", "legal", "bearish"),
        ("Acme CEO steps down", "leadership", "neutral"),
        ("Acme launches new API", "product", "neutral"),
        ("Acme lays off staff after funding round falls through", "layoffs", "bearish"),
        ("A day in the life at Acme", "other", "neutral"),
    ],
)
def test_keywords(title, kind, sentiment):
    v = classify.by_keywords(art(title))
    assert (v.kind, v.sentiment, v.by) == (kind, sentiment, "keywords")


def test_no_key_uses_keywords(monkeypatch):
    verdicts, note = classify.classify("Acme", [], [art("Acme raises $5M")])
    assert verdicts[0].by == "keywords" and note == ""


def test_llm_verdicts_in_order():
    reply = json.dumps(
        {
            "items": [
                {
                    "i": 2,
                    "relevant": False,
                    "sentiment": "neutral",
                    "kind": "other",
                    "explanation": "",
                },
                {
                    "i": 1,
                    "relevant": True,
                    "sentiment": "bullish",
                    "kind": "funding",
                    "explanation": "Fresh funding; teams will grow.",
                },
            ]
        }
    )
    chat = FakeChat(reply)
    arts = [art("Acme raises $5M"), art("Acme-shaped clouds spotted")]
    verdicts, note = classify.classify("Acme", ["Backend Engineer (Payments)"], arts, model=chat)
    assert note == ""
    assert [v.relevant for v in verdicts] == [True, False]
    assert verdicts[0].explanation == "Fresh funding; teams will grow." and verdicts[0].by == "llm"
    system, human = chat.calls[0]
    assert "job seeker" in system[1]
    assert "Applied for: Backend Engineer (Payments)" in human[1]
    assert "1. Acme raises $5M [Reuters] (2026-10-01)" in human[1]


def test_llm_bad_values_are_coerced():
    reply = 'Sure! {"items": [{"i": 1, "sentiment": "VERY GOOD", "kind": "moonshot", "explanation": "x"}]}'
    [v], _ = classify.classify("Acme", [], [art("Acme news")], model=FakeChat(reply))
    assert (v.sentiment, v.kind, v.relevant) == ("neutral", "other", True)


def test_llm_null_explanation_is_empty():
    reply = '{"items": [{"i": 1, "relevant": false, "explanation": null}]}'
    [v], _ = classify.classify("Acme", [], [art("Acme")], model=FakeChat(reply))
    assert v.explanation == ""


def test_llm_missing_items_fall_back_per_headline():
    reply = json.dumps(
        {
            "items": [
                {
                    "i": 1,
                    "relevant": True,
                    "sentiment": "bullish",
                    "kind": "hiring",
                    "explanation": "x",
                },
                {"i": 99},
                {"i": "two"},
            ]
        }
    )
    arts = [art("Acme is hiring"), art("Acme sued by rival")]
    verdicts, note = classify.classify("Acme", [], arts, model=FakeChat(reply))
    assert [v.by for v in verdicts] == ["llm", "keywords"]
    assert verdicts[1].kind == "legal"
    assert note == "LLM skipped 1 headline(s); used keywords"


def test_llm_failure_falls_back_entirely():
    chat = FakeChat(error=TimeoutError("slow"))
    verdicts, note = classify.classify("Acme", [], [art("Acme lays off 10%")], model=chat)
    assert verdicts[0].by == "keywords" and verdicts[0].kind == "layoffs"
    assert note == "LLM unavailable (TimeoutError); used keywords"


def test_llm_garbage_falls_back():
    verdicts, note = classify.classify("Acme", [], [art("x")], model=FakeChat("no json here"))
    assert verdicts[0].by == "keywords"
    assert "skipped 1" in note


def test_nothing_to_classify():
    assert classify.classify("Acme", [], [], model=FakeChat("{}")) == ([], "")
