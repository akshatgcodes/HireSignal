import { useCallback, useEffect, useState } from "react";
import { api, type SignalFilter } from "../api";
import SignalItem from "../components/SignalItem";
import TopBar from "../components/TopBar";
import type { Company, Signal } from "../types";

export default function Signals() {
  const [filter, setFilter] = useState<SignalFilter>({});
  const [signals, setSignals] = useState<Signal[] | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    api
      .signals({ ...filter, limit: 300 })
      .then(setSignals)
      .catch((e) => setError(e.message));
  }, [filter]);
  useEffect(load, [load]);
  useEffect(() => {
    api.companies().then(setCompanies).catch(() => {});
  }, []);

  const set = (patch: SignalFilter) => setFilter((f) => ({ ...f, ...patch }));
  const unread = companies.reduce((n, c) => n + c.unread, 0);

  const toggle = async (s: Signal) => {
    await api.markRead(s.id, !s.read);
    setSignals((list) => list && list.map((x) => (x.id === s.id ? { ...x, read: !s.read } : x)));
    setCompanies((cs) => cs.map((c) => (c.id === s.company_id ? { ...c, unread: c.unread + (s.read ? 1 : -1) } : c)));
  };

  const readAll = async () => {
    await api.markAllRead(filter.company_id);
    api.companies().then(setCompanies);
    load();
  };

  return (
    <>
      <TopBar unread={unread} />
      <main className="page narrow">
        <div className="page-head">
          <h1>Signals</h1>
          <button className="btn" onClick={readAll} disabled={!unread}>
            Mark all read
          </button>
        </div>
        <p className="muted">
          Hiring signals come from comparing each night's job board with the last one. News is from Google News and Hacker News, read by
          the LLM from the point of view of someone with an open application.
        </p>
        <div className="filters" role="group" aria-label="Filters">
          <select value={filter.company_id ?? ""} onChange={(e) => set({ company_id: e.target.value ? Number(e.target.value) : undefined })} aria-label="Company">
            <option value="">All companies</option>
            {companies.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
          <div className="seg">
            {(["", "bullish", "bearish", "neutral"] as const).map((s) => (
              <button key={s} className={(filter.sentiment ?? "") === s ? "on" : ""} onClick={() => set({ sentiment: s || undefined })}>
                {s ? s[0].toUpperCase() + s.slice(1) : "Any"}
              </button>
            ))}
          </div>
          <div className="seg">
            {(["", "hiring", "news"] as const).map((s) => (
              <button key={s} className={(filter.source ?? "") === s ? "on" : ""} onClick={() => set({ source: s || undefined })}>
                {s ? s[0].toUpperCase() + s.slice(1) : "All sources"}
              </button>
            ))}
          </div>
          <label className="check">
            <input type="checkbox" checked={!!filter.unread} onChange={(e) => set({ unread: e.target.checked })} /> Unread only
          </label>
        </div>
        {error && <p className="error">{error}</p>}
        {signals === null ? (
          <p className="muted">Loading…</p>
        ) : signals.length ? (
          <ul className="signals">
            {signals.map((s) => (
              <SignalItem key={s.id} signal={s} onRead={toggle} />
            ))}
          </ul>
        ) : (
          <p className="muted panel empty">No signals match.</p>
        )}
      </main>
    </>
  );
}
