import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import AddCompany from "../components/AddCompany";
import TopBar from "../components/TopBar";
import { ago } from "../lib/board";
import type { Company } from "../types";

export default function Companies() {
  const [companies, setCompanies] = useState<Company[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => {
    api
      .companies()
      .then(setCompanies)
      .catch((e) => setError(e.message));
  };
  useEffect(load, []);

  return (
    <>
      <TopBar unread={companies?.reduce((n, c) => n + c.unread, 0)} />
      <main className="page narrow">
        <h1>Companies</h1>
        <AddCompany onAdded={load} />
        {error && <p className="error">{error}</p>}
        {companies === null ? (
          <p className="muted">Loading…</p>
        ) : companies.length ? (
          <ul className="company-list">
            {companies.map((c) => (
              <li key={c.id} className="panel company-row">
                <div className="company-main">
                  <Link to={`/companies/${c.id}`} className="company-name">
                    {c.name}
                  </Link>
                  <span className="muted small">
                    {c.board ? `${c.board} · ${c.board_slug}` : "news only"} · {c.applications} application{c.applications !== 1 ? "s" : ""}
                  </span>
                  {c.last_error && <span className="error small">{c.last_error}</span>}
                </div>
                <div className="company-nums">
                  <span title="Open roles at the last scan">{c.open_roles ?? "–"} roles</span>
                  <span className="mood">
                    <span className="bullish">▲ {c.sentiment.bullish}</span> <span className="bearish">▼ {c.sentiment.bearish}</span>
                  </span>
                  {c.unread > 0 && <span className="count">{c.unread} new</span>}
                  <span className="muted small">scanned {ago(c.last_scanned_at)}</span>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="muted">No companies yet. Adding an application also adds its company.</p>
        )}
      </main>
    </>
  );
}
