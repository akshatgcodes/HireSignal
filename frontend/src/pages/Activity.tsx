import { useCallback, useEffect, useState } from "react";
import { api } from "../api";
import TopBar from "../components/TopBar";
import { ago } from "../lib/board";
import { useRun } from "../lib/useRun";
import type { Digest, Run } from "../types";

function duration(r: Run): string {
  if (!r.finished_at) return "";
  const s = (new Date(r.finished_at).getTime() - new Date(r.started_at).getTime()) / 1000;
  return s < 60 ? `${s.toFixed(1)}s` : `${Math.floor(s / 60)}m ${Math.round(s % 60)}s`;
}

export default function Activity() {
  const [runs, setRuns] = useState<Run[] | null>(null);
  const [digests, setDigests] = useState<Digest[]>([]);
  const [open, setOpen] = useState<number | null>(null);
  const [preview, setPreview] = useState<Digest | null>(null);
  const [message, setMessage] = useState<{ text: string; error?: boolean } | null>(null);

  const load = useCallback(() => {
    Promise.all([api.runs(), api.digests()])
      .then(([r, d]) => {
        setRuns(r);
        setDigests(d);
      })
      .catch((e) => setMessage({ text: e.message, error: true }));
  }, []);
  useEffect(load, [load]);
  const scan = useRun(load);

  const send = async () => {
    setMessage(null);
    try {
      const d = await api.sendDigest();
      setMessage({ text: d.emailed_to ? `Digest emailed to ${d.emailed_to}.` : "Digest saved. Email isn't set up on the server, so it wasn't sent." });
      load();
    } catch (e) {
      setMessage({ text: e instanceof Error ? e.message : "Couldn't build a digest", error: true });
    }
  };

  const show = async (id: number) => setPreview(await api.digest(id));

  return (
    <>
      <TopBar />
      <main className="page narrow">
        <div className="page-head">
          <h1>Activity</h1>
          <div className="actions">
            <button className="btn" onClick={send}>
              Send digest now
            </button>
            <button className="btn btn-primary" disabled={scan.running} onClick={() => scan.start(api.scanAll)}>
              {scan.running ? "Scanning…" : "Scan all now"}
            </button>
          </div>
        </div>
        {message && <p className={message.error ? "error" : "found"}>{message.text}</p>}
        {scan.error && <p className="error">{scan.error}</p>}

        <h2>Scans</h2>
        {runs === null ? (
          <p className="muted">Loading…</p>
        ) : runs.length ? (
          <ul className="runs">
            {runs.map((r) => (
              <li key={r.id} className="panel run">
                <button className="run-head" onClick={() => setOpen(open === r.id ? null : r.id)} aria-expanded={open === r.id}>
                  <span className={`status ${r.status}`}>{r.status}</span>
                  <span>
                    {r.trigger === "schedule" ? "Nightly" : "Manual"} · {r.stats.companies ?? 0} compan{r.stats.companies === 1 ? "y" : "ies"}
                    {r.stats.new_signals !== undefined && ` · ${r.stats.new_signals} new signals`}
                    {r.stats.failed ? ` · ${r.stats.failed} failed` : ""}
                  </span>
                  <span className="grow" />
                  <span className="muted small">
                    {ago(r.started_at)} {duration(r) && `· ${duration(r)}`}
                  </span>
                </button>
                {open === r.id && r.stats.results && (
                  <table className="results">
                    <thead>
                      <tr>
                        <th>Company</th>
                        <th>Roles</th>
                        <th>Headlines</th>
                        <th>New signals</th>
                        <th>Time</th>
                      </tr>
                    </thead>
                    <tbody>
                      {r.stats.results.map((x, i) => (
                        <tr key={i}>
                          <td>
                            {x.company ?? `#${x.company_id}`}
                            {x.error && <div className="error small">{x.error}</div>}
                            {x.note && <div className="muted small">{x.note}</div>}
                          </td>
                          <td>{x.jobs ?? "–"}</td>
                          <td>{x.news_seen !== undefined ? `${x.news_new} new of ${x.news_seen}` : "–"}</td>
                          <td>{(x.hiring_signals ?? 0) + (x.news_signals ?? 0)}</td>
                          <td>{x.ms !== undefined ? `${(x.ms / 1000).toFixed(1)}s` : ""}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No scans yet. They run nightly, or press Scan all now.</p>
        )}

        <h2>Digests</h2>
        {digests.length ? (
          <ul className="plain digests">
            {digests.map((d) => (
              <li key={d.id}>
                <button className="link-btn" onClick={() => show(d.id)}>
                  {d.subject}
                </button>
                <span className="muted small">
                  {" "}
                  · {ago(d.created_at)} · {d.emailed_to ? `sent to ${d.emailed_to}` : "not emailed"}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No digests yet. One goes out each morning when there's something new.</p>
        )}
        {preview?.html && (
          <section className="panel">
            <div className="panel-head">
              <h2>{preview.subject}</h2>
              <button className="icon-btn" onClick={() => setPreview(null)} aria-label="Close preview">
                ✕
              </button>
            </div>
            {/* The email is our own HTML, but sandboxed anyway: no scripts, no same-origin access */}
            <iframe className="digest-frame" sandbox="allow-popups" srcDoc={preview.html} title="Digest preview" />
          </section>
        )}
      </main>
    </>
  );
}
