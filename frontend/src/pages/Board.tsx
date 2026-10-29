import { useCallback, useEffect, useState, type ReactNode } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import AppDialog from "../components/AppDialog";
import Kanban from "../components/Kanban";
import SignalItem from "../components/SignalItem";
import TopBar from "../components/TopBar";
import { ago, hourLabel, toColumns, type Columns } from "../lib/board";
import { useRun } from "../lib/useRun";
import type { Application, Company, Dashboard, Signal, Status } from "../types";

export default function Board() {
  const [columns, setColumns] = useState<Columns | null>(null);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [dash, setDash] = useState<Dashboard | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [editing, setEditing] = useState<Application | null>(null);
  const [adding, setAdding] = useState<Status | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    Promise.all([api.applications(), api.companies(), api.dashboard(), api.signals({ unread: true, limit: 12 })])
      .then(([apps, cs, d, sigs]) => {
        setColumns(toColumns(apps));
        setCompanies(cs);
        setDash(d);
        setSignals(sigs);
      })
      .catch((e) => setError(e.message));
  }, []);
  useEffect(load, [load]);
  const scan = useRun(load);

  const move = (id: number, status: Status, index: number) => {
    api
      .moveApplication(id, status, index)
      .then(() => api.dashboard().then(setDash))
      .catch((e) => {
        setError(e.message);
        load();
      });
  };

  const saved = () => {
    setEditing(null);
    setAdding(null);
    load();
  };

  const read = async (s: Signal) => {
    await api.markRead(s.id);
    setSignals((list) => list.filter((x) => x.id !== s.id));
    setDash((d) => d && { ...d, unread: Math.max(0, d.unread - 1) });
  };

  const total = columns ? Object.values(columns).reduce((n, c) => n + c.length, 0) : 0;

  return (
    <>
      <TopBar unread={dash?.unread} />
      <main className="page board-page">
        {error && (
          <p className="error banner" onClick={() => setError(null)}>
            {error}
          </p>
        )}
        {dash && (
          <div className="stats">
            <Stat label="Applications" value={total} />
            <Stat label="Response rate" value={dash.response_rate === null ? "–" : `${Math.round(dash.response_rate * 100)}%`} hint="Interview or offer" />
            <Stat label="Follow-ups due" value={dash.follow_ups_due.length} tone={dash.follow_ups_due.length ? "warn" : undefined} />
            <Stat
              label="Signals this week"
              value={
                <span className="mood">
                  <span className="bullish">▲ {dash.signals_7d.bullish}</span> <span className="bearish">▼ {dash.signals_7d.bearish}</span>{" "}
                  <span className="neutral">● {dash.signals_7d.neutral}</span>
                </span>
              }
            />
            <div className="stat scan-stat">
              <span className="label">Last scan</span>
              <span>{scan.running ? "Scanning…" : ago(dash.last_run?.finished_at ?? dash.last_run?.started_at ?? null)}</span>
              <span className="hint">
                Nightly at {hourLabel(dash.schedule.scan_hour)}, digest at {hourLabel(dash.schedule.digest_hour)} ({dash.schedule.timezone})
              </span>
              <button className="btn btn-small" disabled={scan.running || !companies.length} onClick={() => scan.start(api.scanAll)}>
                {scan.running ? "Scanning…" : "Scan now"}
              </button>
            </div>
          </div>
        )}
        {scan.error && <p className="error">{scan.error}</p>}

        <div className="board-layout">
          <div className="board-main">
            {columns === null ? (
              <p className="muted">Loading…</p>
            ) : total === 0 ? (
              <div className="panel empty">
                <h2>Start with one application</h2>
                <p className="muted">
                  Add a role you applied to. Then, on the <Link to="/companies">Companies</Link> page, paste the company's careers link so
                  HireSignal can watch its job board and news.
                </p>
                <button className="btn btn-primary" onClick={() => setAdding("applied")}>
                  Add application
                </button>
              </div>
            ) : (
              <Kanban columns={columns} setColumns={setColumns} onMove={move} onOpen={setEditing} onAdd={setAdding} />
            )}
          </div>
          <aside className="panel signals-panel" aria-label="New signals">
            <div className="panel-head">
              <h2>New signals</h2>
              <Link to="/signals">All</Link>
            </div>
            {signals.length ? (
              <ul className="signals compact">
                {signals.map((s) => (
                  <SignalItem key={s.id} signal={s} onRead={read} />
                ))}
              </ul>
            ) : (
              <p className="muted small">
                {companies.length ? "Nothing new. The next scan runs tonight." : "Signals appear once you track a company."}
              </p>
            )}
          </aside>
        </div>
      </main>
      {(editing || adding) && (
        <AppDialog
          app={editing ?? undefined}
          status={adding ?? undefined}
          companies={companies}
          onClose={() => {
            setEditing(null);
            setAdding(null);
          }}
          onSaved={saved}
          onDeleted={saved}
        />
      )}
    </>
  );
}

function Stat({ label, value, hint, tone }: { label: string; value: ReactNode; hint?: string; tone?: "warn" }) {
  return (
    <div className={`stat${tone ? ` ${tone}` : ""}`}>
      <span className="label">{label}</span>
      <span className="stat-value">{value}</span>
      {hint && <span className="hint">{hint}</span>}
    </div>
  );
}
