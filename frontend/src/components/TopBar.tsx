import { Link, NavLink } from "react-router-dom";
import { Logo, useLogout } from "./RequireOwner";

export default function TopBar({ unread }: { unread?: number }) {
  const logout = useLogout();
  return (
    <header className="topbar">
      <Link to="/" className="logo">
        <Logo /> <span className="logo-text">HireSignal</span>
      </Link>
      <nav className="nav">
        <NavLink to="/" end>
          Board
        </NavLink>
        <NavLink to="/signals">
          Signals{unread ? <span className="count">{unread}</span> : null}
        </NavLink>
        <NavLink to="/companies">Companies</NavLink>
        <NavLink to="/activity">Activity</NavLink>
      </nav>
      <button className="link-btn" onClick={logout}>
        Log out
      </button>
    </header>
  );
}
