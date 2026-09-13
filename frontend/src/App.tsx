import { NavLink, Route, Routes, Navigate, useLocation } from "react-router-dom";
import { ErrorBoundary } from "./components/ErrorBoundary";
import { EngineBanner } from "./components/EngineBanner";
import { InstallPrompt } from "./pwa/InstallPrompt";
import { UpdateToast } from "./pwa/UpdateToast";
import { DataPage } from "./pages/DataPage";
import { AnalyzePage } from "./pages/AnalyzePage";
import { ExplorePage } from "./pages/ExplorePage";
import { GuidedPage } from "./pages/GuidedPage";
import { SpcPage } from "./pages/SpcPage";
import { DocsPage } from "./pages/DocsPage";
import { useApp } from "./state/store";

export default function App() {
  const active = useApp((s) => s.activeDataset);
  const { pathname } = useLocation();

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
          <NavLink to="/spc">SPC</NavLink>
          <NavLink to="/docs">Docs</NavLink>
        </nav>
        <div className="app__ctx">
          {active ? <span className="muted">{active.name}</span> : <span className="muted">no dataset</span>}
        </div>
      </header>

      <EngineBanner />

      <main className="app__main">
        <ErrorBoundary resetKey={pathname}>
        <Routes>
          <Route path="/" element={<Navigate to="/data" replace />} />
          <Route path="/data" element={<DataPage />} />
          <Route path="/guided" element={<GuidedPage />} />
          <Route path="/analyze" element={<AnalyzePage />} />
          <Route path="/explore" element={<ExplorePage />} />
          <Route path="/spc" element={<SpcPage />} />
          <Route path="/docs" element={<DocsPage />} />
          <Route path="*" element={<Navigate to="/data" replace />} />
        </Routes>
        </ErrorBoundary>
      </main>

      <footer className="app__foot muted">
        All computation runs locally in your browser via Pyodide · nothing is uploaded.
      </footer>

      <InstallPrompt />
      <UpdateToast />
    </div>
  );
}
