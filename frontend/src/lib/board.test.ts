import { describe, expect, it } from "vitest";
import type { Application } from "../types";
import { ago, daysUntil, followUp, moveCard, toColumns, todayISO } from "./board";

const card = (id: number, status: Application["status"], position: number): Application => ({
  id,
  status,
  position,
  company_id: 1,
  company: "Acme",
  role: `Role ${id}`,
  team: "",
  job_url: "",
  applied_on: "2026-10-01",
  follow_up_on: null,
  notes: "",
  status_changed_at: "2026-10-01T00:00:00Z",
});

const ids = (cards: Application[]) => cards.map((c) => c.id);

describe("columns", () => {
  const cols = toColumns([card(1, "applied", 2), card(2, "applied", 0), card(3, "interview", 0), card(4, "applied", 1)]);

  it("groups by status and sorts by position", () => {
    expect(ids(cols.applied)).toEqual([2, 4, 1]);
    expect(ids(cols.interview)).toEqual([3]);
    expect(cols.offer).toEqual([]);
  });

  it("moves across columns and updates the card's status", () => {
    const next = moveCard(cols, 4, "interview", 0);
    expect(ids(next.applied)).toEqual([2, 1]);
    expect(ids(next.interview)).toEqual([4, 3]);
    expect(next.interview[0].status).toBe("interview");
    expect(ids(cols.applied)).toEqual([2, 4, 1]); // input untouched
  });

  it("reorders within a column and clamps the index", () => {
    expect(ids(moveCard(cols, 2, "applied", 2).applied)).toEqual([4, 1, 2]);
    expect(ids(moveCard(cols, 2, "applied", 99).applied)).toEqual([4, 1, 2]);
    expect(ids(moveCard(cols, 1, "offer", -3).offer)).toEqual([1]);
  });

  it("ignores unknown cards", () => {
    expect(moveCard(cols, 99, "offer", 0)).toBe(cols);
  });
});

describe("dates", () => {
  const now = new Date(2026, 9, 30, 23, 30); // late evening, local time

  it("counts calendar days, not 24h blocks", () => {
    expect(daysUntil("2026-10-31", now)).toBe(1);
    expect(daysUntil("2026-10-30", now)).toBe(0);
    expect(daysUntil("2026-10-27", now)).toBe(-3);
    expect(todayISO(now)).toBe("2026-10-30");
  });

  it("labels follow-ups", () => {
    expect(followUp(null, now)).toBeNull();
    expect(followUp("2026-10-28", now)).toEqual({ label: "Follow up 2d overdue", tone: "late" });
    expect(followUp("2026-10-30", now)?.tone).toBe("today");
    expect(followUp("2026-10-31", now)?.label).toBe("Follow up tomorrow");
    expect(followUp("2026-11-02", now)?.label).toBe("Follow up in 3d");
    expect(followUp("2026-11-20", now)).toEqual({ label: "Follow up 20 Nov", tone: "later" });
  });

  it("formats relative times", () => {
    const t = Date.parse("2026-10-30T12:00:00Z");
    expect(ago(null, t)).toBe("never");
    expect(ago("2026-10-30T11:59:30Z", t)).toBe("just now");
    expect(ago("2026-10-30T09:00:00Z", t)).toBe("3h ago");
    expect(ago("2026-10-27T12:00:00Z", t)).toBe("3d ago");
  });
});
