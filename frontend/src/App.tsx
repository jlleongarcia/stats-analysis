import { NavLink, Route, Routes, Navigate } from "react-router-dom";
import { EngineBanner } from "./components/EngineBanner";
import { DataPage } from "./pages/DataPage";
import { AnalyzePage } from "./pages/AnalyzePage";
import { ExplorePage } from "./pages/ExplorePage";
import { GuidedPage } from "./pages/GuidedPage";
import { useApp } from "./state/store";

export default function App() {
  const active = useApp((s) => s.activeDataset);

  return (
    <div className="app">
      <header className="app__bar">
        <div className="app__brand">
          <img src="./favicon.svg" width={22} height={22} alt="" />
          <span>Stats Analysis</span>
        </div>
        <nav className="app__nav">
          <NavLink to="/data">Data</NavLink>
          <NavLink to="/guided">Guided</NavLink>
          <NavLink to="/analyze">Analyze</NavLink>
          <NavLink to="/explore">Explore</NavLink>
        </nav>
        <div className="app__ctx">
          {active ? <span className="muted">{active.name}</span> : <span className="muted">no dataset</span>}
        </div>
      </header>

      <EngineBanner />

      <main className="app__main">
        <Routes>
          <Route path="/" element={<Navigate to="/data" replace />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/guided" element={<GuidedPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="*" element={<Navigate to="/data" replace />} />
        </Routes>
      </main>

      <footer className="app__foot muted">
        All computation runs locally in your browser via Pyodide · nothing is uploaded.
      </footer>
    </div>
  );
}
