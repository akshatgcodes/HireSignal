# Decisions

Numbers below come from local runs on 2026-10-30 against the live job boards and feeds, with Groq's `openai/gpt-oss-120b`. Feeds and model output change from day to day, so treat them as observations, not benchmarks.

### 1. No LinkedIn
**Context:** The original plan was to scrape LinkedIn for hiring activity.
**Decision:** HireSignal doesn't touch LinkedIn. Hiring data comes from the public Greenhouse, Lever and Ashby job-board APIs; news from Google News RSS and Hacker News.
**Why:** LinkedIn's terms forbid scraping, most of the useful pages need a logged-in session, and it actively blocks automated access. A tracker that works only until the account is banned isn't worth building. The job-board APIs are documented, unauthenticated, and meant to be read by other sites (they exist so companies can embed their listings).
**Trade-off:** Companies on Workday or another board without a public API get news signals only.

### 2. Hiring signals are computed, not generated
**Decision:** Each scan stores a snapshot of the board (every open role's id, title, team, location, link). Hiring signals come from diffing the last two snapshots with fixed thresholds: any new role in a team you applied to, a team's openings at least halving (from 3 or more), company-wide openings moving 30% or more (from 10 or more), and the posting you applied to disappearing. The first scan only records a baseline.
**Why:** These are counts. A model would add cost and variance to arithmetic, and might describe a change that didn't happen. Fixed wording also keeps the same change from being worded differently every night.
**Trade-off:** Only the newest two snapshots keep their job lists (older ones keep totals for the trend line), so a change is only ever measured against the previous scan.

### 3. One LLM call per company, judged from the applicant's side
**Decision:** All of a company's new headlines go in one call, numbered, with the roles you applied for. The model answers JSON: per headline, relevant or not, bullish/bearish/neutral, a kind, and one sentence on what it means for the application.
**Why:** One call per headline would multiply latency and tokens by 15. Telling the model who is reading changes what "good news" means: a strong quarter for shareholders isn't automatically more hiring.
**How the prompt got there:** The first prompt asked for sentiment "for someone with an open application". On 40 relevant headlines about Stripe, Palantir and OpenAI it marked 23 bullish: product launches, analyst upgrades, "stock is climbing". The second version said most news is neutral and listed what counts as bullish or bearish (funding, layoffs, freezes, results). On the same 40 headlines it gave 7 bullish, 3 bearish and 30 neutral. A later scan still showed two weaknesses, market-research press releases ("…Market Is Going to Boom | Adyen • Stripe • PayPal") marked bullish, and stock predictions too. The third version names both as irrelevant/neutral. On 75 headlines across five companies it kept 41 as relevant, of which 1 was bullish and 2 bearish.
**Trade-off:** A strict prompt means most days produce neutral signals. That is the honest answer for most news, but the digest is quieter than a "sentiment" feature might suggest.

### 4. Off-topic headlines are stored, hidden
**Decision:** Headlines the model calls irrelevant are saved with `relevant = false` and never shown.
**Why:** Feeds return the same stories for days. Without a record, tomorrow's scan would send them to the model again. Dedupe is by feed id and by normalised headline, because Google News and HN (and Google News itself, under different ids) repeat the same story.

### 5. Name matching, and companies named after words
**Decision:** News is searched as `"<name>"` and kept only if the headline contains the name as a whole word. A company can set its own search phrase.
**Why:** The whole-word check removes "pinstripe"-type matches cheaply; the model removes the rest (an Ohio State kicker's "black stripe", an obituary, former employees' startups). Common-word names need more: with the default query, all 15 headlines for Linear were about linear TV, linear algebra or linear actuators, and 12 of 15 for Notion were about "the notion that…". A custom phrase for Linear (`"Linear" ("linear.app" OR "issue tracker" OR Karri)`) returned 2 headlines, both about the company.

### 6. Celery chord, with a shared per-host slot in Redis
**Decision:** The nightly scan is a chord of one task per company on a 4-process worker. Before any request, the fetcher claims a Redis key for that host for 2 seconds (`SET NX PX`); whoever doesn't get it sleeps for the rest of the slot.
**Why:** Companies are independent, so they can run in parallel; the slow parts are network and model calls. Politeness has to be per host, not per process, or four workers would hit Google News four times as often. In the Compose runs, Google News requests from different workers landed 2.0 to 2.3 seconds apart. Four companies took 15 and 18 seconds in two runs, though neither was a clean comparison (in one a company failed on the bug in 9, in the other the LLM budget had run out, see 7). A single-process run with the LLM took 88 seconds for five companies.
**Trade-off:** The chord needs a result backend (Redis). Hosts without a worker can run tasks inline (`CELERY_ALWAYS_EAGER`) and trigger them through `/api/cron/*`.

### 7. The LLM is optional, and failure falls back
**Decision:** Without a key, or if the call fails, a keyword table classifies headlines (ordered, so "lays off … after funding round" reads as layoffs). Each signal records whether it came from a rule, the LLM or keywords.
**Why:** Groq's free tier has a daily token budget (200,000 tokens for this model). One company's classification asked for about 2,500 tokens, so a 15-company night uses roughly 37,000. During testing the budget ran out mid-scan: every company in the run still finished, with a note that keywords were used.

### 8. Fetching user-supplied URLs safely
**Decision:** Detecting a board from a careers page means the server fetches a URL the user typed. That URL must resolve to a public address, and redirects are followed by hand with the same check on each hop.
**Why:** Without it, the API could be pointed at `localhost`, the Docker network or a cloud metadata address. Job-board API calls use fixed hosts and don't need the check.

### 9. Postgres in tests too
**Context:** The first Compose run failed one company with `value too long for type character varying(1000)`: Google News article links can be longer than 1,000 characters. SQLite, used by the tests, doesn't enforce lengths.
**Decision:** The URL column is now `TEXT`, titles and publishers are trimmed to their columns, and the suite runs on Postgres when `TEST_DATABASE_URL` is set (CI does).

---

<div align="center">

<h3>Akshat Gupta</h3>

<a href="https://akshatgcodes.in"><img src="https://img.shields.io/badge/Website-akshatgcodes.in-111111?style=flat-square&logo=googlechrome&logoColor=white" alt="Website"></a>
<a href="https://linkedin.com/in/akshatgcodes"><img src="https://img.shields.io/badge/LinkedIn-akshatgcodes-0A66C2?style=flat-square" alt="LinkedIn"></a>
<a href="https://github.com/akshatgcodes"><img src="https://img.shields.io/badge/GitHub-akshatgcodes-181717?style=flat-square&logo=github&logoColor=white" alt="GitHub"></a>
<a href="mailto:akshatgcodes@gmail.com"><img src="https://img.shields.io/badge/Email-akshatgcodes%40gmail.com-EA4335?style=flat-square&logo=gmail&logoColor=white" alt="Email"></a>

</div>
