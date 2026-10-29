export const STATUSES = ["applied", "interview", "offer", "rejected"] as const;
export type Status = (typeof STATUSES)[number];
export type Sentiment = "bullish" | "bearish" | "neutral";
export type Mood = Record<Sentiment, number>;

export interface Application {
  id: number;
  company_id: number;
  company: string;
  role: string;
  team: string;
  job_url: string;
  status: Status;
  applied_on: string;
  follow_up_on: string | null;
  notes: string;
  position: number;
  status_changed_at: string;
}

export interface Company {
  id: number;
  name: string;
  board: "" | "greenhouse" | "lever" | "ashby";
  board_slug: string;
  careers_url: string;
  news_query: string;
  last_scanned_at: string | null;
  last_error: string;
  applications: number;
  unread: number;
  sentiment: Mood;
  open_roles: number | null;
}

export interface CompanyDetail extends Company {
  trend: { at: string; total: number }[];
  teams: [string, number][];
}

export interface Detected {
  board: Company["board"];
  board_slug: string;
  jobs: number;
  top_teams: [string, number][];
}

export interface Signal {
  id: number;
  company_id: number;
  company: string;
  source: "hiring" | "news";
  kind: string;
  sentiment: Sentiment;
  title: string;
  explanation: string;
  url: string;
  publisher: string;
  classified_by: "llm" | "keywords" | "rule";
  published_at: string | null;
  found_at: string;
  read: boolean;
}

export interface RunResult {
  company?: string;
  company_id?: number;
  jobs?: number;
  hiring_signals?: number;
  news_seen?: number;
  news_new?: number;
  news_signals?: number;
  note?: string;
  error?: string;
  ms?: number;
}

export interface Run {
  id: number;
  trigger: "schedule" | "manual";
  status: "running" | "done" | "failed";
  started_at: string;
  finished_at: string | null;
  stats: { companies?: number; failed?: number; new_signals?: number; results?: RunResult[] };
}

export interface Digest {
  id: number;
  created_at: string;
  trigger: string;
  subject: string;
  signal_count: number;
  follow_ups: number;
  emailed_to: string;
  html?: string;
}

export interface Dashboard {
  by_status: Record<Status, number>;
  response_rate: number | null;
  signals_7d: Mood;
  unread: number;
  follow_ups_due: Application[];
  last_run: Run | null;
  schedule: { timezone: string; scan_hour: number; digest_hour: number; emails_to: string };
  llm: string;
}
