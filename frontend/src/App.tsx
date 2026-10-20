import type { ReactNode } from "react";
import { useEffect, useState } from "react";
import { NavLink, Route, Routes, Link } from "react-router-dom";
import {
  AudioLines,
  LayoutDashboard,
  FolderKanban,
  Video,
  Settings2,
  Moon,
  Sun,
  Plus,
  Menu,
  X,
  ShieldCheck,
} from "lucide-react";
import { Button } from "./components/ui/button";
import { useData } from "./components/shared";
import {
  Dashboard,
  Projects,
  ProjectDetail,
  NewMeeting,
  Meetings,
} from "./pages/projects";
import { MeetingPage, TranscriptPage, ResultsPage } from "./pages/meetings";
import { SettingsPage } from "./pages/settings";

export default function App({
  settingsPage,
  environmentLabel = "Entorno local",
}: {
  settingsPage?: ReactNode;
  environmentLabel?: string;
}) {
  const [dark, setDark] = useState(
    () => localStorage.getItem("mra-theme") === "dark",
  );
  const [menu, setMenu] = useState(false);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("mra-theme", dark ? "dark" : "light");
  }, [dark]);
  const health = useData<{ worker_online: boolean }>("/health", true);
  return (
    <div className="app-shell">
      <aside className={"sidebar " + (menu ? "sidebar-open" : "")}>
        <Link to="/" className="brand">
          <span className="brand-icon">
            <AudioLines size={25} />
          </span>
          <span>
            meeting<span className="brand-sub">REQUIREMENTS AI</span>
          </span>
        </Link>
        <div className="workspace-label">ESPACIO DE TRABAJO</div>
        <nav>
          {[
            [LayoutDashboard, "/", "Vista general"],
            [FolderKanban, "/projects", "Proyectos"],
            [Video, "/meetings", "Reuniones"],
            [Settings2, "/settings", "Configuración"],
          ].map(([Icon, to, name]) => {
            const I = Icon as typeof AudioLines;
            return (
              <NavLink
                key={String(to)}
                to={String(to)}
                end={to === "/"}
                onClick={() => setMenu(false)}
              >
                <I size={19} />
                <span>{String(name)}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="privacy-note">
            <ShieldCheck size={19} />
            <strong>Tu audio se queda aquí</strong>
            <p>Transcripción local. Tú decides qué texto compartir.</p>
          </div>
          <div className="worker-status">
            <span
              className={
                "status-dot " + (health.data?.worker_online ? "online" : "")
              }
            />
            {health.data?.worker_online
              ? "Worker disponible"
              : "Worker sin conexión"}
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <div className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label="Menú"
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="topbar-label">
            De la conversación a la especificación.
          </span>
          <div className="topbar-actions">
            <span className="local-tag">
              <span /> {environmentLabel}
            </span>
            <button
              className="icon-button"
              aria-label="Cambiar tema"
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={19} /> : <Moon size={19} />}
            </button>
            <Button asChild size="sm">
              <Link to="/meetings/new">
                <Plus size={16} />
                Nueva reunión
              </Link>
            </Button>
          </div>
        </div>
        <main>
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/projects" element={<Projects />} />
            <Route path="/projects/:id" element={<ProjectDetail />} />
            <Route path="/meetings" element={<Meetings />} />
            <Route path="/meetings/new" element={<NewMeeting />} />
            <Route path="/meetings/:id" element={<MeetingPage />} />
            <Route
              path="/meetings/:id/transcript"
              element={<TranscriptPage />}
            />
            <Route path="/meetings/:id/results" element={<ResultsPage />} />
            <Route
              path="/settings"
              element={settingsPage ?? <SettingsPage />}
            />
            <Route
              path="*"
              element={
                <div className="empty">
                  <h1>Página no encontrada</h1>
                  <Link to="/">Volver al inicio</Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer>
          Meeting Requirements AI{" "}
          <span>
            Grabaciones corporativas: utiliza únicamente archivos cuyo
            procesamiento esté autorizado.
          </span>
        </footer>
      </div>
    </div>
  );
}
