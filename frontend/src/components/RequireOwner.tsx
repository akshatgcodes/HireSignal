import { createContext, useContext, useEffect, useState, type FormEvent } from "react";
import { Outlet } from "react-router-dom";
import { api } from "../api";

const LogoutContext = createContext<() => void>(() => {});
export const useLogout = () => useContext(LogoutContext);

export default function RequireOwner() {
  const [owner, setOwner] = useState<boolean | null>(null);
  const [apiDown, setApiDown] = useState(false);

  useEffect(() => {
    api.me().then((r) => setOwner(r.owner)).catch(() => setApiDown(true));
  }, []);

  if (apiDown) return <div className="center error">Can't reach the HireSignal API. Is the backend running?</div>;
  if (owner === null) return <div className="center muted">Loading…</div>;
  if (!owner) return <LoginScreen onDone={() => setOwner(true)} />;

  const logout = async () => {
    await api.logout();
    setOwner(false);
  };
  return (
    <LogoutContext.Provider value={logout}>
      <Outlet />
    </LogoutContext.Provider>
  );
}

export function Logo({ size = 22 }: { size?: number }) {
  return (
    <svg width={size} height={size} viewBox="0 0 32 32" aria-hidden>
      <rect width="32" height="32" rx="7" fill="var(--accent)" />
      <path d="M6 21h4l3-9 4 13 3-8h6" fill="none" stroke="#fff" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

function LoginScreen({ onDone }: { onDone: () => void }) {
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);

  const submit = async (e: FormEvent) => {
    e.preventDefault();
    try {
      await api.login(password);
      onDone();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    }
  };

  return (
    <main className="center">
      <form className="panel login" onSubmit={submit}>
        <h1 className="logo big">
          <Logo size={28} /> HireSignal
        </h1>
        <p className="muted">Track your job applications on a board, and get a morning email when the companies you applied to start hiring, freeze, raise money or lay people off.</p>
        <label className="label" htmlFor="pw">
          Password
        </label>
        <input id="pw" type="password" value={password} onChange={(e) => setPassword(e.target.value)} autoFocus required />
        {error && <p className="error">{error}</p>}
        <button className="btn btn-primary" type="submit">
          Log in
        </button>
      </form>
    </main>
  );
}
