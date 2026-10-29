# Deploy

HireSignal is **not deployed yet**. These are the two intended setups.

## One server (the full design)

`docker compose up -d --build` on a small VM, with TLS in front of the `web` service. In an `.env` next to the Compose file:

- `APP_PASSWORD`, `SESSION_SECRET` (long random values)
- `GROQ_API_KEY` or `LLM_API_KEY`
- `DIGEST_TO` and real `SMTP_*` settings; then remove the `mailpit` service, or at least stop publishing port 8025
- `PUBLIC_URL` set to the public address

## Free tiers (no worker)

Free web-service tiers usually can't run a separate worker and beat. The API can run tasks itself:

| Part | Option |
|---|---|
| Frontend | Vercel (`frontend/`, build `npm run build`, output `dist`, SPA rewrite to `index.html`, `VITE_API_URL` set) |
| API | Render web service from `backend/Dockerfile` |
| Database | Neon Postgres |
| Schedule | any outside scheduler calling the cron routes |

API settings: `CELERY_ALWAYS_EAGER=true`, no `REDIS_URL`, `CRON_SECRET` (long random), `FRONTEND_URL` and `CROSS_SITE_COOKIES=true`, plus the ones above. Then schedule two calls, for example from GitHub Actions:

```bash
curl -X POST -H "X-Cron-Secret: $CRON_SECRET" https://<api-host>/api/cron/scan
curl -X POST -H "X-Cron-Secret: $CRON_SECRET" https://<api-host>/api/cron/digest
```

In this mode companies are scanned one after another inside that request (88 seconds for five companies in a local run), and request spacing is per process, which is fine with a single process. Free instances that sleep take a while to wake on the first call.

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
