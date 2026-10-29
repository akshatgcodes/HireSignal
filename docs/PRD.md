# PRD: HireSignal

## Problem

After applying to a dozen companies, the waiting is the hard part. A spreadsheet tracks where each application stands, but it can't tell you that the team you applied to just posted three more roles, that the company froze hiring last week, or that the posting you applied to quietly came down. That information is public, scattered across job boards and news sites, and nobody checks all of it every day.

## Goal

A job application tracker that also watches the companies on it. Applications live on a Kanban board. Every night HireSignal checks each company's public job board and recent news, turns what changed into a short list of signals (bullish, bearish or neutral, each with a one-line explanation), and emails a morning digest with the signals and any follow-ups that are due.

## Users

- A student or engineer running an active job search across 5 to 30 companies
- Someone waiting on a few applications who wants to know when to nudge a recruiter

## User stories

| As a… | I want to… | So that… |
|---|---|---|
| job seeker | drag applications between Applied, Interview, Offer and Rejected | the board shows where everything stands |
| job seeker | set a follow-up date on each application, with a sensible default | I don't forget to check in |
| job seeker | paste a careers page and have the job board found for me | I don't need to know what Greenhouse or Ashby is |
| job seeker | hear when the team I applied to adds or removes roles | I know whether it's still hiring |
| job seeker | hear when the posting I applied to is taken down | I'm not surprised by the outcome |
| job seeker | see news about each company, judged for what it means for my application | I skip the stock-price noise |
| job seeker | get one email each morning | I don't have to open the app to stay current |
| job seeker | scan now and see what each scan did | I can trust the nightly job |

## Requirements

- Kanban with four columns, drag and drop with the mouse or the keyboard, order kept on the server
- Follow-up dates: default 7 days after applying, 3 days after moving to Interview, none for Offer or Rejected
- Job boards: Greenhouse, Lever and Ashby public APIs; detection from a board link or a careers page that embeds or links one
- News: Google News RSS and Hacker News (Algolia) per company, last 30 days, whole-word match on the name
- Hiring signals computed from snapshot diffs (no LLM); news signals classified by an LLM with a keyword fallback
- Nightly scan and morning digest on a schedule (Celery beat), scans run in parallel on a worker
- Polite fetching: at most one request every 2 seconds per host across all workers, retries with backoff, an identifying User-Agent
- Signals deduplicated across nights and across feeds; off-topic headlines remembered so they're not re-classified
- Owner password login; works without an LLM key and without SMTP

## Non-goals

- LinkedIn or any source that needs a login or forbids automated access (see [Decisions](DECISIONS.md#1-no-linkedin))
- Applying to jobs, or job search and recommendations
- Multiple users
- Workday, iCIMS and other boards without a public JSON API
- Predicting the outcome of an application

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
