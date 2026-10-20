import { t, useI18n } from "./lib/i18n";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
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
import { LanguageSelector } from "./components/language-selector";
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
  environmentLabel = t("Entorno local"),
  privacyTitle = t("Tu audio se queda aquí"),
  privacyDescription = t(
    "Transcripción local. Tú decides qué texto compartir.",
  ),
}: {
  settingsPage?: ReactNode;
  environmentLabel?: string;
  privacyTitle?: string;
  privacyDescription?: string;
}) {
  useI18n();
  const [dark, setDark] = useState(
    () => localStorage.getItem("mra-theme") === "dark",
  );
  const [menu, setMenu] = useState(false);
  const [mobile, setMobile] = useState(
    () => window.matchMedia?.("(max-width: 760px)").matches ?? false,
  );
  const sidebar = useRef<HTMLElement>(null);
  useEffect(() => {
    const media = window.matchMedia?.("(max-width: 760px)");
    if (!media) return;
    const update = () => {
      setMobile(media.matches);
      setMenu(false);
    };
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  useEffect(() => {
    if (!menu || !mobile) return;
    const previous = document.activeElement as HTMLElement | null;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    const focusable = () =>
      Array.from(
        sidebar.current?.querySelectorAll<HTMLElement>(
          "a[href], button:not([disabled]), select:not([disabled])",
        ) ?? [],
      ).filter((el) => el.getClientRects().length);
    focusable()[0]?.focus();
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setMenu(false);
      }
      if (event.key !== "Tab") return;
      const items = focusable();
      const first = items[0],
        last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last?.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first?.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
      previous?.focus();
    };
  }, [menu, mobile]);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("mra-theme", dark ? "dark" : "light");
  }, [dark]);
  const health = useData<{ worker_online: boolean }>("/health", true);
  return (
    <div className="app-shell">
      <a href="#main-content" className="skip-link">
        {t("Saltar al contenido")}
      </a>
      {mobile && menu && (
        <button
          className="nav-backdrop"
          aria-label={t("Cerrar navegación")}
          onClick={() => setMenu(false)}
          tabIndex={-1}
        />
      )}
      <aside
        ref={sidebar}
        id="workspace-navigation"
        aria-label={t("Navegación del espacio de trabajo")}
        role={mobile && menu ? "dialog" : undefined}
        aria-modal={mobile && menu ? true : undefined}
        inert={mobile && !menu}
        className={"sidebar " + (menu ? "sidebar-open" : "")}
      >
        <button
          className="icon-button mobile-menu sidebar-close"
          aria-label={t("Cerrar navegación")}
          onClick={() => setMenu(false)}
        >
          <X size={20} />
        </button>
        <Link to="/" className="brand">
          <span className="brand-icon">
            <AudioLines size={25} />
          </span>
          <span>
            meeting<span className="brand-sub">REQUIREMENTS AI</span>
          </span>
        </Link>
        <div className="workspace-label">{t("ESPACIO DE TRABAJO")}</div>
        <nav aria-label={t("Navegación principal")}>
          {[
            [LayoutDashboard, "/", t("Vista general")],
            [FolderKanban, "/projects", t("Proyectos")],
            [Video, "/meetings", t("Reuniones")],
            [Settings2, "/settings", t("Configuración")],
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
        <LanguageSelector className="sidebar-language" />
        <div className="sidebar-bottom">
          <div className="privacy-note">
            <ShieldCheck size={19} />
            <strong>{privacyTitle}</strong>
            <p>{privacyDescription}</p>
          </div>
          <div className="worker-status" role="status">
            <span
              className={
                "status-dot " + (health.data?.worker_online ? "online" : "")
              }
            />
            {health.isPending
              ? t("Comprobando worker…")
              : health.error
                ? t("Estado no disponible")
                : health.data?.worker_online
                  ? t("Worker disponible")
                  : t("Worker sin conexión")}
          </div>
        </div>
      </aside>
      <div className="main-shell" inert={mobile && menu}>
        <div className="topbar">
          <button
            className="icon-button mobile-menu"
            aria-label={t("Abrir navegación")}
            aria-expanded={menu}
            aria-controls="workspace-navigation"
            onClick={() => setMenu(!menu)}
          >
            {menu ? <X size={20} /> : <Menu size={20} />}
          </button>
          <span className="topbar-label">
            {t("De la conversación a la especificación.")}
          </span>
          <div className="topbar-actions">
            <LanguageSelector className="desktop-language" />
            <span className="local-tag">
              <span /> {environmentLabel}
            </span>
            <button
              className="icon-button"
              aria-label={
                dark ? t("Activar tema claro") : t("Activar tema oscuro")
              }
              onClick={() => setDark(!dark)}
            >
              {dark ? <Sun size={19} /> : <Moon size={19} />}
            </button>
            <Button asChild size="sm">
              <Link to="/meetings/new">
                <Plus size={16} />
                {t("Nueva reunión")}
              </Link>
            </Button>
          </div>
        </div>
        <main id="main-content" tabIndex={-1}>
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
                  <h1>{t("Página no encontrada")}</h1>
                  <Link to="/">{t("Volver al inicio")}</Link>
                </div>
              }
            />
          </Routes>
        </main>
        <footer>
          Meeting Requirements AI{" "}
          <span>
            {t(
              "Grabaciones corporativas: utiliza únicamente archivos cuyo procesamiento esté autorizado.",
            )}
          </span>
        </footer>
      </div>
    </div>
  );
}
