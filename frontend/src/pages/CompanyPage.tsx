import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import SignalItem from "../components/SignalItem";
import Sparkline from "../components/Sparkline";
import TopBar from "../components/TopBar";
import { ago, shortDate } from "../lib/board";
import { useRun } from "../lib/useRun";
import type { Application, CompanyDetail, Signal } from "../types";

export default function CompanyPage() {
  const id = Number(useParams().id);
  const navigate = useNavigate();
  const [c, setC] = useState<CompanyDetail | null>(null);
  const [apps, setApps] = useState<Application[]>([]);
  const [signals, setSignals] = useState<Signal[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);

  const load = useCallback(() => {
    Promise.all([api.company(id), api.applications(), api.signals({ company_id: id, limit: 200 })])
      .then(([company, all, sigs]) => {
        setC(company);
        setApps(all.filter((a) => a.company_id === id));
        setSignals(sigs);
      })
      .catch((e) => setError(e.message));
  }, [id]);
  useEffect(load, [load]);
  const scan = useRun(load);

  const toggle = async (s: Signal) => {
    await api.markRead(s.id, !s.read);
    setSignals((list) => list.map((x) => (x.id === s.id ? { ...x, read: !s.read } : x)));
  };

  const remove = async () => {
    if (!c || !confirm(`Stop tracking ${c.name}? Its ${c.applications} application(s) and all signals are deleted too.`)) return;
    await api.removeCompany(c.id);
    navigate("/companies");
  };

  if (error) return <p className="center error">{error}</p>;
  if (!c) return <p className="center muted">Loading…</p>;
  const lastResult = scan.run?.stats.results?.[0];
  const maxTeam = c.teams[0]?.[1] ?? 1;

  return (
    <>
      <TopBar />
      <main className="page narrow">
        <Link to="/companies" className="muted small">
          ← Companies
        </Link>
        <div className="page-head">
          <h1>{c.name}</h1>
          <div className="actions">
            <button className="btn" onClick={() => setEditing((e) => !e)}>
              Settings
            </button>
            <button className="btn btn-primary" disabled={scan.running} onClick={() => scan.start(() => api.scanCompany(c.id))}>
              {scan.running ? "Scanning…" : "Scan now"}
            </button>
          </div>
        </div>
        <p className="muted small">
          {c.board ? (
            <>
              {c.board} board <code>{c.board_slug}</code>
            </>
          ) : (
            "No job board: news only"
          )}{" "}
          · last scanned {ago(c.last_scanned_at)}
        </p>
        {c.last_error && <p className="error">Last scan: {c.last_error}</p>}
        {scan.error && <p className="error">{scan.error}</p>}
        {lastResult && !scan.running && (
          <p className="found">
            Scan done: {lastResult.jobs !== undefined && `${lastResult.jobs} roles, `}
            {(lastResult.hiring_signals ?? 0) + (lastResult.news_signals ?? 0)} new signals
            {lastResult.note && ` (${lastResult.note})`}.
          </p>
        )}
        {editing && <Settings company={c} onSaved={() => (setEditing(false), load())} onDelete={remove} />}

        <div className="grid2">
          <section className="panel">
            <h2>Open roles</h2>
            {c.open_roles === null ? (
              <p className="muted small">{c.board ? "Not scanned yet." : "Add a job board link in Settings to watch hiring."}</p>
            ) : (
              <>
                <div className="big-num">{c.open_roles}</div>
                <Sparkline points={c.trend.map((t) => t.total)} />
                {c.trend.length < 2 && <p className="hint">The trend line appears after the second scan.</p>}
                <ul className="bars">
                  {c.teams.slice(0, 10).map(([team, n]) => (
                    <li key={team}>
                      <span className="bar-label">{team}</span>
                      <span className="bar" style={{ width: `${(n / maxTeam) * 100}%` }} />
                      <span className="bar-n">{n}</span>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </section>
          <section className="panel">
            <h2>Your applications</h2>
            {apps.length ? (
              <ul className="plain">
                {apps.map((a) => (
                  <li key={a.id}>
                    <b>{a.role}</b> {a.team && <span className="chip">{a.team}</span>}
                    <div className="muted small">
                      {a.status} · applied {shortDate(a.applied_on)}
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <p className="muted small">None yet.</p>
            )}
          </section>
        </div>

        <h2>Signals</h2>
        {signals.length ? (
          <ul className="signals">
            {signals.map((s) => (
              <SignalItem key={s.id} signal={s} onRead={toggle} showCompany={false} />
            ))}
          </ul>
        ) : (
          <p className="muted">No signals yet. Run a scan to fetch the job board and news.</p>
        )}
      </main>
    </>
  );
}

function Settings({ company: c, onSaved, onDelete }: { company: CompanyDetail; onSaved: () => void; onDelete: () => void }) {
  const [url, setUrl] = useState(c.careers_url);
  const [board, setBoard] = useState<string>(c.board);
  const [slug, setSlug] = useState(c.board_slug);
  const [query, setQuery] = useState(c.news_query);
  const [error, setError] = useState<string | null>(null);
  const [note, setNote] = useState<string | null>(null);

  const detect = async () => {
    setError(null);
    try {
      const d = await api.detect(url);
      setBoard(d.board);
      setSlug(d.board_slug);
      setNote(`Found ${d.jobs} roles on ${d.board}.`);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't check that link");
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.updateCompany(c.id, { careers_url: url, board: board as CompanyDetail["board"], board_slug: board ? slug : "", news_query: query });
      onSaved();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
    }
  };

  return (
    <form className="panel form" onSubmit={submit}>
      <label>
        <span className="label">Careers page or job board link</span>
        <div className="inline">
          <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://…" />
          <button type="button" className="btn" onClick={detect} disabled={!url}>
            Find board
          </button>
        </div>
      </label>
      <div className="row2">
        <label>
          <span className="label">Board</span>
          <select value={board} onChange={(e) => setBoard(e.target.value)}>
            <option value="">None (news only)</option>
            <option value="greenhouse">Greenhouse</option>
            <option value="lever">Lever</option>
            <option value="ashby">Ashby</option>
          </select>
        </label>
        <label>
          <span className="label">Board slug</span>
          <input value={slug} onChange={(e) => setSlug(e.target.value)} disabled={!board} placeholder="stripe" />
        </label>
      </div>
      <label>
        <span className="label">News search</span>
        <input value={query} onChange={(e) => setQuery(e.target.value)} placeholder={`"${c.name}"`} />
        <span className="hint">For names that are also common words, try something like "Box Inc" OR "box.com".</span>
      </label>
      {note && <p className="found">{note}</p>}
      {error && <p className="error">{error}</p>}
      <p className="hint">Changing the board clears its saved snapshots, so the next scan starts a new baseline.</p>
      <div className="actions">
        <button type="button" className="btn btn-danger" onClick={onDelete}>
          Stop tracking
        </button>
        <span className="grow" />
        <button className="btn btn-primary">Save</button>
      </div>
    </form>
  );
}
