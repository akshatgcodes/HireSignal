import type { Site } from "./types";

export const site: Site = {
  name: "HireSignal",
  letter: "H",
  title: "HireSignal — know when the companies you applied to change course",
  description:
    "A job application tracker that watches the companies you applied to. Every night it reads their job boards and the news, works out what changed, and tells you in the morning when a team starts hiring, freezes, raises money or lays people off.",
  meta: ["live", "applications + company signals", "GPLv3"],
  headline: ["Your applications, and", "what changed at those companies."],
  intro:
    "A Kanban board for your job applications that also watches every company on it. Each night it reads their job boards and the news, and each morning it tells you when a team starts hiring, freezes, raises money or lays people off.",
  primary: { label: "Open HireSignal", href: "/app/" },
  repo: "https://github.com/akshatgcodes/HireSignal",
  note: "Demo password: `demo1234`. The live demo scans every night from a GitHub Actions schedule; digests are shown in the app instead of emailed.",
  xfactor: {
    title: "Signals from snapshots, not guesses.",
    intro:
      "Hiring signals are plain arithmetic on what the job boards said last night and the night before. The model only reads the news.",
    features: [
      {
        icon: "▦",
        title: "Job board snapshots",
        body: "Paste a careers page and it finds the Greenhouse, Lever or Ashby board behind it. New roles in your team, openings halving, hiring swinging 30%, or your posting coming down.",
      },
      {
        icon: "◐",
        title: "News, read for you",
        body: "Google News and Hacker News headlines naming the company, read by an LLM as someone waiting on an application would. Stock chatter is neutral; funding, layoffs and freezes are not.",
      },
      {
        icon: "✉",
        title: "One morning summary",
        body: "New signals grouped by company, each with a one-line explanation, plus the follow-ups that are due today.",
      },
    ],
  },
  preview: {
    intro: "The board with follow-up dates and the latest signals beside it, the signals feed with filters, and a digest.",
    shots: [
      { src: "/shots/board.png", alt: "Kanban board of applications with follow-up badges and a signals list", caption: "Board" },
      { src: "/shots/signals.png", alt: "Signals feed with bullish, bearish and neutral filters", caption: "Signals" },
      { src: "/shots/digest.png", alt: "A morning digest with signals by company and due follow-ups", caption: "Digest" },
    ],
  },
  stack: ["React 19", "TypeScript", "Vite", "dnd-kit", "FastAPI", "SQLAlchemy", "PostgreSQL", "Celery", "Redis", "LangChain", "Groq", "BeautifulSoup", "pytest", "Vitest"],
  concepts: [
    { title: "One task per company", body: "A Celery chord fans out a scan task for each company and collects the results, so one slow job board doesn't hold up the rest." },
    { title: "Polite scraping", body: "One request every 2 seconds per host across all workers, retries with backoff, an identifying User-Agent, and no logins scraped." },
    { title: "Works without a key", body: "Without an LLM key, headlines are classified by a keyword table; the hiring signals never needed the model." },
    { title: "Automatic follow-ups", body: "A week after applying, three days after moving to Interview, none after an offer or rejection; editable per card." },
    { title: "Runs without a worker too", body: "On free hosts the API runs the scan inside a request, triggered by a GitHub Actions schedule with a shared secret." },
    { title: "Company pages", body: "Open roles, their trend across scans, the biggest teams, your applications there and every signal." },
  ],
  run: {
    title: "Run your own",
    intro: "Docker Compose starts Postgres, Redis, the API, a Celery worker and beat, Mailpit and the app.",
    blocks: [
      {
        title: "Docker",
        steps: [
          { text: "Clone; a Groq key is optional:", cmd: "git clone https://github.com/akshatgcodes/HireSignal\ncd HireSignal\nexport GROQ_API_KEY=..." },
          { text: "Start everything:", cmd: "docker compose up --build" },
          { text: "Open the app; morning emails land in Mailpit:", cmd: "http://localhost:5173\nhttp://localhost:8025" },
        ],
      },
    ],
  },
  tagline: "an application tracker that watches the companies.",
};
