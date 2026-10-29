import { Route, Routes } from "react-router-dom";
import RequireOwner from "./components/RequireOwner";
import Activity from "./pages/Activity";
import Board from "./pages/Board";
import Companies from "./pages/Companies";
import CompanyPage from "./pages/CompanyPage";
import Signals from "./pages/Signals";

export default function App() {
  return (
    <Routes>
      <Route element={<RequireOwner />}>
        <Route path="/" element={<Board />} />
        <Route path="/signals" element={<Signals />} />
        <Route path="/companies" element={<Companies />} />
        <Route path="/companies/:id" element={<CompanyPage />} />
        <Route path="/activity" element={<Activity />} />
      </Route>
    </Routes>
  );
}
