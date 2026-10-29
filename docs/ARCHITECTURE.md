# Architecture

```
                 ┌───────────── docker compose ─────────────────────────────────┐
 browser ──▶ web (nginx: React build, /api proxy) ──▶ api (FastAPI)              │
                 │                                     │  board, companies,      │
                 │                                     │  signals, runs, digests │
                 │                                     ▼                         │
                 │   beat ──02:00──▶ redis (broker) ──▶ worker ×4 (Celery)       │
                 │         08:00                         │                       │
                 │                                       ├─ job boards (JSON)    │
                 │                                       ├─ Google News (RSS)    │
                 │                                       ├─ Hacker News (JSON)   │
                 │                                       └─ LLM (Groq)           │
                 │   postgres ◀── api, worker            mailpit ◀── digest      │
                 └───────────────────────────────────────────────────────────────┘
```

## A nightly run

1. **beat** puts `nightly_scan` on the queue at `SCAN_HOUR` in `TIMEZONE`.
2. `nightly_scan` creates a `Run` row and starts a Celery **chord**: one `scan_company` task per company, with `finish_run` as the callback.
3. Workers pick up companies in parallel. For each one, `pipeline.scan_company`:
   - **Job board** (if set): fetch every open role → build `{id: {title, team, location, url}}` → diff against the previous snapshot (`signals.diff`) → save the new snapshot and the hiring signals.
   - **News**: fetch Google News RSS and HN, keep headlines that name the company as a whole word, drop duplicates by normalised headline, drop ones already seen (by feed id or headline) → classify the rest in **one LLM call** → save relevant ones as signals, and irrelevant ones as hidden rows so they aren't classified again.
   - The two halves fail separately; errors are stored on the company and in the run.
4. `finish_run` gets every company's stats and writes them to the run in one go.
5. At `DIGEST_HOUR`, `send_digest` collects signals not yet in a digest plus follow-ups due today or earlier, renders HTML and text, saves the digest and sends it over SMTP.

Every outgoing request goes through `http.Fetcher`: one shared Redis slot per host (`SET NX PX 2000`), so four workers still reach `news.google.com` one request at a time, about 2 seconds apart; retries with exponential backoff on timeouts, 429 and 5xx, honouring `Retry-After` (capped at 2 minutes).

## Backend modules

| Module | Role |
|---|---|
| `http.py` | `Fetcher` (spacing, retries, User-Agent), `HostSpacing` (Redis or in-process), `check_public_url` and `Fetcher.page` (user-supplied URLs: public addresses only, every redirect re-checked) |
| `sources/boards.py` | Board detection from links or page HTML; parsers for the three APIs → `Job(id, title, team, location, url)` |
| `sources/news.py` | Google News RSS (BeautifulSoup, `xml` parser) and HN parsers, name matching, headline dedupe |
| `signals.py` | Snapshot diff → hiring signals: baseline, team growth/shrink, company-wide swing, posting closed |
| `classify.py` | LLM prompt and parsing, keyword table fallback |
| `pipeline.py` | One company's scan, snapshot pruning, dedupe against stored signals |
| `tasks.py` | Celery app, beat schedule, `start_run` / `scan_company` / `finish_run` / `send_digest` |
| `digest.py`, `mail.py` | Digest selection, HTML + text rendering, SMTP |
| `routers/` | REST API; `cron.py` for hosts without a worker |

## Data model

| Table | Key columns |
|---|---|
| `companies` | name (unique), board, board_slug, careers_url, news_query, last_scanned_at, last_error |
| `applications` | company_id, role, team, job_url, status, applied_on, follow_up_on, notes, position, status_changed_at |
| `job_snapshots` | company_id, taken_at, total, by_team (JSON), jobs (JSON; kept only on the newest two) |
| `signals` | company_id, source (`hiring`/`news`), kind, sentiment, title, explanation, url, publisher, external_id (unique per company), classified_by (`rule`/`llm`/`keywords`), relevant, read, digest_id |
| `runs` | trigger, status, started_at, finished_at, stats (JSON, one entry per company) |
| `digests` | trigger, subject, html, signal_count, follow_ups, emailed_to |

Tables are created on API start (`create_all`); there are no migrations yet.

## API

All under `/api`; everything except login and the cron routes needs the owner session.

| Method | Path | |
|---|---|---|
| POST | `/auth/login` · `/auth/logout` · GET `/auth/me` | |
| GET · POST | `/applications` | create with `company_id` or `company_name` (creates the company) |
| PATCH · DELETE | `/applications/{id}` | |
| POST | `/applications/{id}/move` | `{status, index}`; renumbers the target column |
| GET · POST | `/companies` | list includes open roles, unread count, sentiment counts |
| POST | `/companies/detect` | `{url}` → board, slug, job count, top teams |
| GET · PATCH · DELETE | `/companies/{id}` | detail includes the open-roles trend and teams |
| POST | `/companies/{id}/scan` | starts a one-company run |
| GET | `/signals` | filters: `company_id`, `sentiment`, `source`, `unread`, `limit` |
| POST | `/signals/{id}/read` · `/signals/read-all` | |
| GET · POST | `/runs` · GET `/runs/{id}` | POST scans every company |
| GET · POST | `/digests` · GET `/digests/{id}` | POST builds and sends one now |
| GET | `/dashboard` · `/follow-ups` | |
| POST | `/cron/scan` · `/cron/digest` | `X-Cron-Secret` header; off unless `CRON_SECRET` is set |

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
