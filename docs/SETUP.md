# Setup

## Requirements

- Docker (for the Compose setup), or:
- Python 3.12 and [uv](https://docs.astral.sh/uv/), Node 20.19+ or 22.12+ (what Vite 8 needs), and Redis if you want a real worker
- Optional: an API key for an OpenAI-compatible provider ([Groq](https://console.groq.com/keys) has a free tier). Without one, headlines are classified by keywords.

## Everything with Docker

```bash
export GROQ_API_KEY=...          # optional
docker compose up --build
```

- App: http://localhost:5173 (password `hiresignal` unless you set `APP_PASSWORD`)
- Mailpit (catches the digest emails): http://localhost:8025

Services: `db` (Postgres 17), `redis`, `api`, `worker` (Celery, 4 processes), `beat` (schedule), `web` (nginx serving the build and proxying `/api`), `mailpit`.

## Without Docker

```bash
cd backend
uv sync
cp .env.example .env      # set APP_PASSWORD and SESSION_SECRET
uv run uvicorn main:app --reload
```

With `CELERY_ALWAYS_EAGER=true` (the default in `.env.example`) and no `REDIS_URL`, "Scan now" runs inside the API request: no worker, no Redis, SQLite in the backend folder. To run it like Compose does, set `REDIS_URL=redis://localhost:6379/0`, `CELERY_ALWAYS_EAGER=false`, and start:

```bash
uv run celery -A app.tasks worker --concurrency 4
uv run celery -A app.tasks beat
```

```bash
cd frontend
npm install
npm run dev               # http://localhost:5173, proxies /api to :8000
```

`VITE_API_PROXY=http://localhost:8005 npm run dev` points the proxy elsewhere; `VITE_API_URL` is for a build served apart from the API.

## Settings

| Variable | Default | Purpose |
|---|---|---|
| `DATABASE_URL` | SQLite file | e.g. `postgresql+psycopg://…` |
| `REDIS_URL` | empty | Celery broker and result backend, and the shared per-host request slot |
| `CELERY_ALWAYS_EAGER` | `false` | run tasks inline in the API process |
| `APP_PASSWORD` | empty | login password; login is refused until it's set |
| `SESSION_SECRET` | dev value | signs the session cookie; set a long random string |
| `FRONTEND_URL` | `http://localhost:5173` | allowed CORS origin |
| `CROSS_SITE_COOKIES` | `false` | `true` when frontend and API are on different sites (HTTPS) |
| `PUBLIC_URL` | `http://localhost:5173` | link in the digest email |
| `TIMEZONE` | `Asia/Kolkata` | for the schedule and "today" in follow-ups |
| `SCAN_HOUR` / `DIGEST_HOUR` | `2` / `8` | when beat runs the scan and the digest |
| `DIGEST_TO` | empty | recipient; empty saves digests without sending |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_STARTTLS`, `MAIL_FROM` | | outgoing mail |
| `LLM_API_KEY` / `GROQ_API_KEY` | empty | empty = keyword classification |
| `LLM_BASE_URL` / `LLM_MODEL` | Groq / `openai/gpt-oss-120b` | any OpenAI-compatible endpoint |
| `LLM_MAX_TOKENS` | `4000` | output budget per company, reasoning included |
| `HOST_INTERVAL` | `2.0` | seconds between requests to the same host |
| `NEWS_DAYS` / `NEWS_PER_COMPANY` | `30` / `15` | news window and how many headlines per company |
| `USER_AGENT` | `HireSignal/0.1 (personal job tracker)` | sent with every request |
| `CRON_SECRET` | empty | enables `/api/cron/scan` and `/api/cron/digest` |

## Checks

```bash
cd backend && uv run ruff check . && uv run ruff format --check . && uv run pytest
cd frontend && npm run typecheck && npm test && npm run build
```

The backend tests use saved, trimmed responses from the real APIs (`tests/fixtures/`), an `httpx.MockTransport`, a fake chat model and eager Celery: no network, no key, no Redis. Set `TEST_DATABASE_URL=postgresql+psycopg://…` to run them on Postgres.

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
