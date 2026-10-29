import { useState, type FormEvent } from "react";
import { api, type ApplicationInput } from "../api";
import { todayISO } from "../lib/board";
import type { Application, Company, Status } from "../types";
import Modal from "./Modal";

export default function AppDialog({
  app,
  status = "applied",
  companies,
  onClose,
  onSaved,
  onDeleted,
}: {
  app?: Application;
  status?: Status;
  companies: Company[];
  onClose: () => void;
  onSaved: (a: Application) => void;
  onDeleted?: (id: number) => void;
}) {
  const [company, setCompany] = useState(app?.company ?? "");
  const [role, setRole] = useState(app?.role ?? "");
  const [team, setTeam] = useState(app?.team ?? "");
  const [jobUrl, setJobUrl] = useState(app?.job_url ?? "");
  const [appliedOn, setAppliedOn] = useState(app?.applied_on ?? todayISO());
  const [followUp, setFollowUp] = useState(app?.follow_up_on ?? "");
  const [notes, setNotes] = useState(app?.notes ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    const body: ApplicationInput = {
      role,
      team,
      job_url: jobUrl,
      applied_on: appliedOn,
      notes,
      // Empty means "pick a sensible default" when creating, and "no reminder" when editing
      ...(followUp ? { follow_up_on: followUp } : app ? { follow_up_on: null } : {}),
    };
    try {
      if (app) {
        onSaved(await api.updateApplication(app.id, body));
      } else {
        const known = companies.find((c) => c.name.toLowerCase() === company.trim().toLowerCase());
        onSaved(
          await api.createApplication({ ...body, status, ...(known ? { company_id: known.id } : { company_name: company.trim() }) }),
        );
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Couldn't save");
      setBusy(false);
    }
  };

  const remove = async () => {
    if (!app || !confirm(`Delete ${app.role} at ${app.company}?`)) return;
    await api.removeApplication(app.id);
    onDeleted?.(app.id);
  };

  return (
    <Modal title={app ? "Edit application" : "New application"} onClose={onClose}>
      <form className="form" onSubmit={submit}>
        <label>
          <span className="label">Company</span>
          <input
            list="companies"
            value={company}
            onChange={(e) => setCompany(e.target.value)}
            disabled={!!app}
            required
            autoFocus={!app}
            placeholder="Stripe"
          />
          <datalist id="companies">
            {companies.map((c) => (
              <option key={c.id} value={c.name} />
            ))}
          </datalist>
        </label>
        <label>
          <span className="label">Role</span>
          <input value={role} onChange={(e) => setRole(e.target.value)} required placeholder="Backend Engineer" />
        </label>
        <div className="row2">
          <label>
            <span className="label">Team</span>
            <input value={team} onChange={(e) => setTeam(e.target.value)} placeholder="Payments" />
            <span className="hint">Matched against the job board's teams for hiring signals.</span>
          </label>
          <label>
            <span className="label">Job link</span>
            <input type="url" value={jobUrl} onChange={(e) => setJobUrl(e.target.value)} placeholder="https://…" />
            <span className="hint">Lets HireSignal tell you if the posting comes down.</span>
          </label>
        </div>
        <div className="row2">
          <label>
            <span className="label">Applied on</span>
            <input type="date" value={appliedOn} onChange={(e) => setAppliedOn(e.target.value)} required />
          </label>
          <label>
            <span className="label">Follow up on</span>
            <input type="date" value={followUp} onChange={(e) => setFollowUp(e.target.value)} />
            {!app && <span className="hint">Empty: a week after applying.</span>}
          </label>
        </div>
        <label>
          <span className="label">Notes</span>
          <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Recruiter name, referral, salary range…" />
        </label>
        {error && <p className="error">{error}</p>}
        <div className="actions">
          {app && (
            <button type="button" className="btn btn-danger" onClick={remove}>
              Delete
            </button>
          )}
          <span className="grow" />
          <button type="button" className="btn" onClick={onClose}>
            Cancel
          </button>
          <button className="btn btn-primary" disabled={busy}>
            {app ? "Save" : "Add"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
