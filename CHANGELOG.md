# Changelog

All notable changes to **HireSignal** are documented here.

---

## [Unreleased]

---

## [0.1.0] — 2026-10-30

### ✨ Added
- Kanban board for applications with drag and drop, ordering kept on the server, and follow-up dates with defaults per stage
- Companies with job-board detection from a board link or a careers page (Greenhouse, Lever, Ashby)
- Nightly scan on Celery beat: job-board snapshots diffed into hiring signals; Google News and Hacker News headlines classified by an LLM (keyword fallback)
- Morning digest email with new signals and due follow-ups
- Signals feed with filters and read state, company pages with open-role trend and teams, scan and digest history
- Polite HTTP client: per-host spacing shared through Redis, retries with backoff, public-address check for user-supplied URLs
- Docker Compose with Postgres, Redis, worker, beat, nginx and Mailpit; cron routes for hosts without a worker

### 🧪 Tests
- Parsers against trimmed real responses from every source, the HTTP client's retries and spacing, every hiring-signal rule, the classifier with a fake model, full scans, and the API end to end with eager Celery
- Kanban column moves and date labels

---

[Unreleased]: https://github.com/akshatgcodes/HireSignal/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/akshatgcodes/HireSignal/releases/tag/v0.1.0

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
