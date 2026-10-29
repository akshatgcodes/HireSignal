"""Turns headlines into signals: is it about this company, is it good or bad news for
someone waiting on an application there, and why.

One LLM call per company per night, with all its new headlines in it. Without an API
key (or if the call fails) a keyword table does a rougher job, so scans never stall.
"""

import json
import logging
import re
from dataclasses import dataclass

from app.config import settings
from app.sources.news import Article

log = logging.getLogger("hiresignal.classify")

KINDS = (
    "funding",
    "layoffs",
    "hiring",
    "leadership",
    "earnings",
    "acquisition",
    "product",
    "partnership",
    "legal",
    "other",
)

SYSTEM = """You help a job seeker read the news about companies they applied to.

For each numbered headline, decide:
- relevant: is it actually about the company named? Not relevant: namesakes, sports,
  obituaries, former employees' new ventures, and market-research press releases that
  list many companies ("X Market Is Going to Boom | A • B • C").
- sentiment, from the point of view of someone with an open application there. Most news
  is neutral; pick bullish or bearish only when the headline points to a change in how
  much the company is hiring or the money behind it.
  bullish: funding, a hiring push, new offices, strong results, fast expansion.
  bearish: layoffs, hiring freezes, big losses, cost cutting, a crisis that threatens the
  business, leaders leaving in a hurry.
  neutral: product launches, partnerships, routine acquisitions, opinion pieces,
  incidents and bugs, community posts. Share-price moves, analyst ratings, price targets
  and stock predictions are neutral too, however excited the wording: they say nothing
  about hiring.
- kind: one of funding, layoffs, hiring, leadership, earnings, acquisition, product,
  partnership, legal, other.
- explanation: one short sentence on what this means for the application (not a restatement
  of the headline). Use only what the headline says; don't invent numbers or details.

Answer with JSON only:
{"items": [{"i": 1, "relevant": true, "sentiment": "neutral", "kind": "product",
"explanation": "..."}]}"""


@dataclass
class Verdict:
    relevant: bool
    sentiment: str
    kind: str
    explanation: str
    by: str  # llm | keywords


# Ordered: the first match wins, so "lays off ... after funding round" reads as layoffs.
# (pattern, kind, sentiment, explanation)
KEYWORDS: list[tuple[str, str, str, str]] = [
    (
        r"\blay(?:s|ing)? off|layoffs?\b|job cuts|cuts? \d[\d,]* (?:jobs|roles|staff)"
        r"|workforce reduction|redundanc",
        "layoffs",
        "bearish",
        "Layoffs usually mean fewer open roles for a while.",
    ),
    (
        r"hiring freeze|freezes hiring|pauses hiring",
        "hiring",
        "bearish",
        "A hiring freeze can stall open applications.",
    ),
    (
        r"\braises?\b.*\$|\bfunding\b|series [a-h]\b|valuation|\bipo\b",
        "funding",
        "bullish",
        "New money usually turns into new roles.",
    ),
    (
        r"\bhiring\b|\bto hire\b|new office|expands? (?:to|into)|opens? .*office",
        "hiring",
        "bullish",
        "Growth news: teams are likely adding people.",
    ),
    (
        r"\bacquir|acquisition|\bbuys\b|to buy\b|merger",
        "acquisition",
        "neutral",
        "Deals can reshuffle teams; watch for re-orgs.",
    ),
    (
        r"lawsuit|\bsued\b|\bsues\b|probe|investigation|\bfine[ds]?\b|antitrust",
        "legal",
        "bearish",
        "Legal trouble can slow hiring decisions.",
    ),
    (
        r"\bceo\b|\bcto\b|\bcfo\b|steps? down|resigns?|appoint|names .* (?:chief|head)",
        "leadership",
        "neutral",
        "Leadership changes can shift team priorities.",
    ),
    (
        r"earnings|revenue|quarter|profit|\bloss\b",
        "earnings",
        "neutral",
        "Financial results; check whether they beat or missed.",
    ),
    (r"launch|unveil|introduc|release", "product", "neutral", "Product news; no hiring signal."),
    (r"partner", "partnership", "neutral", "A partnership; no direct hiring signal."),
]
KEYWORD_RES = [(re.compile(p, re.I), k, s, e) for p, k, s, e in KEYWORDS]


def by_keywords(article: Article) -> Verdict:
    for rx, kind, sentiment, why in KEYWORD_RES:
        if rx.search(article.title):
            return Verdict(True, sentiment, kind, why, "keywords")
    return Verdict(True, "neutral", "other", "General news; no clear hiring signal.", "keywords")


def chat_model():
    from langchain_openai import ChatOpenAI

    return ChatOpenAI(
        model=settings.llm_model,
        api_key=settings.llm_key,
        base_url=settings.llm_base_url,
        temperature=0,
        max_tokens=settings.llm_max_tokens,
        timeout=60,
        max_retries=2,
        model_kwargs={"response_format": {"type": "json_object"}},
    )


def _prompt(company: str, roles: list[str], articles: list[Article]) -> str:
    lines = [f"Company: {company}"]
    if roles:
        lines.append("Applied for: " + "; ".join(roles))
    lines.append("")
    for i, a in enumerate(articles, 1):
        when = f" ({a.published_at:%Y-%m-%d})" if a.published_at else ""
        lines.append(f"{i}. {a.title} [{a.publisher}]{when}")
    return "\n".join(lines)


def _parse(raw: str, n: int) -> dict[int, Verdict]:
    start, end = raw.find("{"), raw.rfind("}")
    data = json.loads(raw[start : end + 1]) if start != -1 else {}
    out = {}
    for item in data.get("items", []):
        try:
            i = int(item["i"])
        except (KeyError, TypeError, ValueError):
            continue
        sentiment = str(item.get("sentiment", "neutral")).lower()
        kind = str(item.get("kind", "other")).lower()
        if 1 <= i <= n:
            out[i] = Verdict(
                relevant=bool(item.get("relevant", True)),
                sentiment=sentiment
                if sentiment in ("bullish", "bearish", "neutral")
                else "neutral",
                kind=kind if kind in KINDS else "other",
                explanation=str(item.get("explanation") or "").strip()[:600],
                by="llm",
            )
    return out


def classify(
    company: str, roles: list[str], articles: list[Article], model=None
) -> tuple[list[Verdict], str]:
    """One verdict per article, in order, plus a note when the LLM couldn't be used."""
    if not articles:
        return [], ""
    if model is None and not settings.llm_key:
        return [by_keywords(a) for a in articles], ""
    try:
        model = model or chat_model()
        reply = model.invoke([("system", SYSTEM), ("human", _prompt(company, roles, articles))])
        got = _parse(
            reply.content if isinstance(reply.content, str) else str(reply.content), len(articles)
        )
    except Exception as e:  # noqa: BLE001 — any provider/parse failure falls back
        log.warning("LLM classification failed for %s: %s", company, e)
        return [
            by_keywords(a) for a in articles
        ], f"LLM unavailable ({type(e).__name__}); used keywords"
    missing = [i for i in range(1, len(articles) + 1) if i not in got]
    note = f"LLM skipped {len(missing)} headline(s); used keywords" if missing else ""
    return [got.get(i) or by_keywords(articles[i - 1]) for i in range(1, len(articles) + 1)], note
