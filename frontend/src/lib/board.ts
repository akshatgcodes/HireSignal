// Pure helpers for the Kanban board and dates, kept out of components so they can be tested.
import { STATUSES, type Application, type Status } from "../types";

export type Columns = Record<Status, Application[]>;

export function toColumns(apps: Application[]): Columns {
  const cols = Object.fromEntries(STATUSES.map((s) => [s, [] as Application[]])) as Columns;
  for (const a of apps) cols[a.status]?.push(a);
  for (const s of STATUSES) cols[s].sort((x, y) => x.position - y.position || x.id - y.id);
  return cols;
}

export function findCard(cols: Columns, id: number): { status: Status; index: number } | null {
  for (const s of STATUSES) {
    const index = cols[s].findIndex((a) => a.id === id);
    if (index !== -1) return { status: s, index };
  }
  return null;
}

/** Moves a card to `index` in column `to` (clamped), returning new columns. */
export function moveCard(cols: Columns, id: number, to: Status, index: number): Columns {
  const from = findCard(cols, id);
  if (!from) return cols;
  const card = cols[from.status][from.index];
  const next = { ...cols, [from.status]: cols[from.status].filter((a) => a.id !== id) } as Columns;
  const target = [...next[to]];
  target.splice(Math.max(0, Math.min(index, target.length)), 0, { ...card, status: to });
  next[to] = target;
  return next;
}

/** Parses "YYYY-MM-DD" as a local calendar date (new Date("2026-10-01") would be UTC). */
export function localDate(iso: string): Date {
  const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
  return new Date(y, m - 1, d);
}

export function todayISO(now = new Date()): string {
  const p = (n: number) => String(n).padStart(2, "0");
  return `${now.getFullYear()}-${p(now.getMonth() + 1)}-${p(now.getDate())}`;
}

export function daysUntil(iso: string, now = new Date()): number {
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return Math.round((localDate(iso).getTime() - today.getTime()) / 86_400_000);
}

export type FollowUp = { label: string; tone: "late" | "today" | "soon" | "later" };

export function followUp(iso: string | null, now = new Date()): FollowUp | null {
  if (!iso) return null;
  const d = daysUntil(iso, now);
  if (d < 0) return { label: `Follow up ${-d}d overdue`, tone: "late" };
  if (d === 0) return { label: "Follow up today", tone: "today" };
  if (d === 1) return { label: "Follow up tomorrow", tone: "soon" };
  if (d <= 3) return { label: `Follow up in ${d}d`, tone: "soon" };
  return { label: `Follow up ${shortDate(iso)}`, tone: "later" };
}

export function shortDate(iso: string): string {
  return localDate(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short" });
}

/** "3h ago", "2d ago" for UTC timestamps. */
export function ago(iso: string | null, now = Date.now()): string {
  if (!iso) return "never";
  const s = Math.max(0, (now - new Date(iso).getTime()) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 30) return `${Math.floor(s / 86400)}d ago`;
  return new Date(iso).toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" });
}

export function hourLabel(h: number): string {
  return `${String(h).padStart(2, "0")}:00`;
}
