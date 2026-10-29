import { Link } from "react-router-dom";
import { ago } from "../lib/board";
import type { Signal } from "../types";

const ARROW = { bullish: "▲", bearish: "▼", neutral: "●" } as const;
const KIND: Record<string, string> = {
  team_growth: "team growth",
  team_shrink: "team shrinking",
  hiring_slowdown: "hiring slowdown",
  hiring_growth: "hiring growth",
  posting_closed: "posting closed",
  baseline: "tracking started",
};

export default function SignalItem({
  signal: s,
  onRead,
  showCompany = true,
}: {
  signal: Signal;
  onRead?: (s: Signal) => void;
  showCompany?: boolean;
}) {
  return (
    <li className={`signal ${s.sentiment}${s.read ? " read" : ""}`}>
      <span className="arrow" aria-label={s.sentiment} title={s.sentiment}>
        {ARROW[s.sentiment]}
      </span>
      <div className="signal-body">
        <div className="signal-title">
          {s.url ? (
            <a href={s.url} target="_blank" rel="noreferrer noopener">
              {s.title}
            </a>
          ) : (
            s.title
          )}
        </div>
        {s.explanation && <p className="signal-why">{s.explanation}</p>}
        <div className="signal-meta">
          {showCompany && (
            <Link to={`/companies/${s.company_id}`} className="chip">
              {s.company}
            </Link>
          )}
          <span className={`tag ${s.source}`}>{KIND[s.kind] ?? s.kind}</span>
          {s.publisher && <span>{s.publisher}</span>}
          <span title={s.published_at ?? s.found_at}>{ago(s.published_at ?? s.found_at)}</span>
          {s.classified_by === "keywords" && <span title="Classified by keyword rules, not the LLM">keywords</span>}
        </div>
      </div>
      {onRead && (
        <button className="icon-btn" onClick={() => onRead(s)} title={s.read ? "Mark unread" : "Mark read"} aria-label={s.read ? "Mark unread" : "Mark read"}>
          {s.read ? "○" : "✓"}
        </button>
      )}
    </li>
  );
}
