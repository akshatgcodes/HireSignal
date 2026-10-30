<p align="center">
  <svg xmlns="http://www.w3.org/2000/svg" width="64" height="64" viewBox="0 0 24 24"
       fill="none" stroke="#0f766e" stroke-width="1.5"
       stroke-linecap="round" stroke-linejoin="round">
    <path d="M3 15h3l2.5-7 3.5 11 2.5-6.5H21"/>
  </svg>
</p>

<h1 align="center">HireSignal</h1>

<p align="center">
  <strong>A job application tracker that watches the companies you applied to. Every night it reads their job boards and the news, works out what changed, and emails you in the morning when a team starts hiring, freezes, raises money or lays people off.</strong>
</p>

<p align="center">
  <a href="https://hiresignal.akshatgcodes.in">
    <img src="https://img.shields.io/badge/live_demo-0f766e-0f766e?style=flat-square" alt="Live Demo">
  </a>
  <img src="https://img.shields.io/badge/React-20232A?style=flat-square&logo=react&logoColor=61DAFB" alt="React">
  <img src="https://img.shields.io/badge/TypeScript-3178C6?style=flat-square&logo=typescript&logoColor=white" alt="TypeScript">
  <img src="https://img.shields.io/badge/FastAPI-009688?style=flat-square&logo=fastapi&logoColor=white" alt="FastAPI">
  <img src="https://img.shields.io/badge/PostgreSQL-4169E1?style=flat-square&logo=postgresql&logoColor=white" alt="PostgreSQL">
  <img src="https://img.shields.io/badge/Celery-37814A?style=flat-square&logo=celery&logoColor=white" alt="Celery">
  <img src="https://img.shields.io/badge/Redis-DC382D?style=flat-square&logo=redis&logoColor=white" alt="Redis">
  <img src="https://img.shields.io/badge/LangChain-1C3C3C?style=flat-square&logo=langchain&logoColor=white" alt="LangChain">
  <img src="https://img.shields.io/badge/license-GPL--3.0-0f766e?style=flat-square" alt="License">
</p>

---

## What is HireSignal?

A Kanban board for your applications (Applied → Interview → Offer → Rejected) with follow-up dates, plus a nightly job that keeps an eye on every company on it:

1. **Job boards.** Paste a careers page and HireSignal finds the Greenhouse, Lever or Ashby board behind it (it did for Notion, Linear and Figma; Stripe's own jobs page doesn't link its board, so that one needs the board link). Each night it takes a snapshot of every open role and compares it with the last one: new roles in the team you applied to, a team's openings halving, company-wide hiring swinging 30%, or your posting coming down.
2. **News.** Google News and Hacker News headlines from the last 30 days that name the company. An LLM reads them as someone waiting on an application would: is this about the company at all, and does it make hiring more or less likely? The prompt tells it that stock chatter and product launches are neutral, and funding, layoffs and freezes are not.
3. **The morning email.** New signals grouped by company, each with a one-line explanation, and the follow-ups that are due.

Hiring signals are plain arithmetic on the snapshots, so they don't depend on the model. Without an LLM key, headlines are classified by a keyword table instead.

> **Live demo →** [hiresignal.akshatgcodes.in](https://hiresignal.akshatgcodes.in)
> Log in with the demo password `demo1234`. It scans every night from a GitHub Actions schedule; digests show in the app instead of being emailed. The free host sleeps when idle, so the first load can take up to a minute.

---

## What you get

- **Kanban board** with drag and drop (mouse or keyboard), cards showing team, applied date and follow-up status (overdue / today / soon)
- **Automatic follow-ups**: a week after applying, three days after moving to Interview, none after an offer or rejection; editable per card
- **Signals feed** with bullish / bearish / neutral, source and read filters; a short list beside the board
- **Company pages**: open roles, their trend across scans, biggest teams, your applications there, every signal
- **Activity page**: each scan with per-company results (roles, headlines, new signals, errors, time), digests with an inline preview, "scan now" and "send digest now"
- **Polite by design**: one request every 2 seconds per host across all workers, retries with backoff, an identifying User-Agent, no logins scraped
- **Dark mode**, works on phones

---

## Stack

| Layer | Tech |
|---|---|
| Frontend | React 19 · TypeScript · Vite · React Router · dnd-kit |
| Backend | FastAPI · SQLAlchemy · PostgreSQL |
| Jobs | Celery worker + beat on Redis; a chord fans out one task per company |
| Sources | Greenhouse, Lever and Ashby public APIs · Google News RSS · Hacker News (Algolia) · httpx · BeautifulSoup |
| LLM | LangChain `ChatOpenAI` against Groq (`openai/gpt-oss-120b`) or any OpenAI-compatible endpoint |
| Email | SMTP; Mailpit catches it locally |
| Tooling | uv · pytest · Vitest · ruff · Docker Compose · GitHub Actions |

---

## Run it

```bash
export GROQ_API_KEY=...        # optional
docker compose up --build
```

App on http://localhost:5173 (password `hiresignal`), caught emails on http://localhost:8025. Without Docker, see [docs/SETUP.md](docs/SETUP.md).

---

## Engineering Decisions

**Why not LinkedIn?**
Its terms forbid scraping, the useful pages need a login, and it blocks automated access, so a tracker built on it works until the account is banned. The Greenhouse, Lever and Ashby APIs are documented, unauthenticated and meant to be read by other sites. Companies on boards without such an API get news signals only.

**Why isn't the LLM deciding the hiring signals?**
They're counts: roles that appeared, roles that vanished, totals per team. Computing them is exact, free and worded the same way every night. The model is used where judgement is needed, deciding whether a headline is about the company and whether it matters for an application.

**How did the classifier prompt change?**
The first version, asked for sentiment "for someone with an open application", marked 23 of 40 relevant headlines bullish, mostly product launches and analyst upgrades. Spelling out what moves hiring (funding, layoffs, freezes, results) and that share-price talk is neutral brought the same 40 down to 7 bullish and 3 bearish. A later version also drops market-research press releases that list a dozen companies. Details in [Decisions](docs/DECISIONS.md#3-one-llm-call-per-company-judged-from-the-applicants-side).

**What broke on Postgres that tests missed?**
Google News article links can run past 1,000 characters. SQLite ignored the column size; Postgres rejected the insert and one company's scan failed. The column is `TEXT` now and CI runs the backend suite on Postgres.

**What would you do differently in v2?**
Re-classify headlines that fell back to keywords once the LLM budget is back, and let a company have several boards (some use one board per region).

More in [docs/DECISIONS.md](docs/DECISIONS.md).

---

## Docs

| Document | Description |
|---|---|
| [PRD](docs/PRD.md) | Product requirements: goals, user stories, non-goals |
| [Architecture](docs/ARCHITECTURE.md) | Nightly run, modules, data model, API |
| [Decisions](docs/DECISIONS.md) | Every major technical decision and why |
| [Setup](docs/SETUP.md) | Docker and local setup, settings |
| [Deploy](docs/DEPLOY.md) | Deployment notes |
| [Contributing](CONTRIBUTING.md) | How to propose changes |
| [Changelog](CHANGELOG.md) | What changed in each release |
| [Security](SECURITY.md) | How to report a vulnerability |

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
