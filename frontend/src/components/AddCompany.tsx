import { useState, type FormEvent } from "react";
import { api } from "../api";
import type { Company, Detected } from "../types";

const BOARD_NAMES = { greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby", "": "" } as const;

export default function AddCompany({ onAdded }: { onAdded: (c: Company) => void }) {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [found, setFound] = useState<Detected | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState<"detect" | "save" | null>(null);

  const detect = async () => {
    if (!url.trim()) return;
    setBusy("detect");
    setError(null);
    setFound(null);
    try {
      setFound(await api.detect(url));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't check that link");
    } finally {
      setBusy(null);
    }
  };

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy("save");
    setError(null);
    try {
      const c = await api.createCompany({
        name: name.trim(),
        careers_url: url.trim(),
        ...(found ? { board: found.board, board_slug: found.board_slug } : {}),
      });
      setName("");
      setUrl("");
      setFound(null);
      onAdded(c);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't add");
    } finally {
      setBusy(null);
    }
  };

  return (
    <form className="panel add-company" onSubmit={submit}>
      <h2>Track a company</h2>
      <div className="row2">
        <label>
          <span className="label">Name</span>
          <input value={name} onChange={(e) => setName(e.target.value)} required placeholder="Stripe" />
        </label>
        <label>
          <span className="label">Careers page or job board link</span>
          <div className="inline">
            <input
              value={url}
              onChange={(e) => {
                setUrl(e.target.value);
                setFound(null);
              }}
              onBlur={() => url && !found && detect()}
              placeholder="https://stripe.com/jobs or boards.greenhouse.io/stripe"
            />
            <button type="button" className="btn" onClick={detect} disabled={!url || busy !== null}>
              {busy === "detect" ? "Checking…" : "Find board"}
            </button>
          </div>
        </label>
      </div>
      {found && (
        <p className="found">
          ✓ {BOARD_NAMES[found.board]} board <code>{found.board_slug}</code> with {found.jobs} open roles. Biggest teams:{" "}
          {found.top_teams
            .slice(0, 5)
            .map(([t, n]) => `${t} (${n})`)
            .join(", ")}
        </p>
      )}
      {error && <p className="error">{error}</p>}
      <p className="hint">Works with Greenhouse, Lever and Ashby boards. Without one, HireSignal still watches the news.</p>
      <button className="btn btn-primary" disabled={busy !== null || !name.trim()}>
        Add company
      </button>
    </form>
  );
}
