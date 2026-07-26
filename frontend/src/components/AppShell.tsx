import {
  Aperture,
  BookOpenText,
  Bot,
  Boxes,
  ChevronDown,
  CircleGauge,
  Command,
  FileStack,
  FlaskConical,
  Menu,
  Moon,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  Settings,
  Sparkles,
  Sun,
  UploadCloud,
  Video,
  X,
} from "lucide-react";
import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { getRagConfiguration } from "../api/client";
import type { RagConfiguration } from "../types";

const navigation = [
  { to: "/landing", label: "Product Showcase", icon: Sparkles, end: true },
  { to: "/", label: "Overview", icon: CircleGauge, end: true },
  { to: "/knowledge-bases", label: "Knowledge", icon: Boxes, end: false },
  { to: "/upload", label: "Source library", icon: FileStack, end: false },
  { to: "/chat", label: "Research chat", icon: Bot, end: false },
  { to: "/video", label: "Video intelligence", icon: Video, end: false },
  { to: "/intelligence", label: "Compare & reports", icon: FlaskConical, end: false },
  { to: "/evaluation", label: "Evaluation", icon: CircleGauge, end: false },
  { to: "/feedback", label: "Feedback", icon: Sparkles, end: false },
  { to: "/templates", label: "Templates", icon: BookOpenText, end: false },
];

export function AppShell({ children }: { children: ReactNode }) {
  const currentPath = window.location.pathname;
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [commandOpen, setCommandOpen] = useState(false);
  const [modelConfiguration, setModelConfiguration] =
    useState<RagConfiguration | null>(null);
  const [modelConfigurationChecked, setModelConfigurationChecked] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => {
    const saved = window.localStorage.getItem("enterprise-rag-theme");
    return saved === "dark" ? "dark" : "light";
  });

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    window.localStorage.setItem("enterprise-rag-theme", theme);
  }, [theme]);

  useEffect(() => {
    let active = true;
    const refresh = () => {
      getRagConfiguration()
        .then((value) => {
          if (active) setModelConfiguration(value);
        })
        .catch(() => {
          if (active) setModelConfiguration(null);
        })
        .finally(() => {
          if (active) setModelConfigurationChecked(true);
        });
    };
    refresh();
    const interval = window.setInterval(refresh, 15_000);
    return () => {
      active = false;
      window.clearInterval(interval);
    };
  }, []);

  useEffect(() => {
    const listener = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setCommandOpen((value) => !value);
      }
      if (event.key === "/" && document.activeElement?.tagName === "BODY") {
        event.preventDefault();
        setCommandOpen(true);
      }
      if (event.key === "Escape") {
        setCommandOpen(false);
        setMobileOpen(false);
      }
    };
    window.addEventListener("keydown", listener);
    return () => window.removeEventListener("keydown", listener);
  }, []);

  function runCommand(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const query = new FormData(event.currentTarget).get("query")?.toString().trim();
    if (query) {
      window.location.href = `/chat?question=${encodeURIComponent(query)}`;
    }
  }

  return (
    <div className={`app-shell ${collapsed ? "sidebar-collapsed" : ""}`}>
      <button
        className="mobile-nav-trigger icon-button"
        onClick={() => setMobileOpen(true)}
        aria-label="Open navigation"
      >
        <Menu size={19} />
      </button>
      {mobileOpen && (
        <button
          className="mobile-scrim"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation"
        />
      )}
      <aside className={`sidebar ${mobileOpen ? "mobile-open" : ""}`}>
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">
            <Aperture size={20} />
          </span>
          <span className="brand-copy">
            <strong>EnterpriseRAG</strong>
            <small>Knowledge intelligence</small>
          </span>
          <button
            className="sidebar-close icon-button"
            onClick={() => setMobileOpen(false)}
            aria-label="Close navigation"
          >
            <X size={18} />
          </button>
        </div>

        <button className="workspace-switcher" title="Local intelligence workspace">
          <span className="workspace-avatar">ER</span>
          <span className="brand-copy">
            <small>Workspace</small>
            <strong>Local intelligence</strong>
          </span>
          <ChevronDown className="brand-copy" size={15} />
        </button>

        <a className="sidebar-create" href="/upload">
          <Plus size={16} />
          <span className="brand-copy">Add knowledge</span>
        </a>

        <nav aria-label="Primary navigation">
          <span className="nav-caption brand-copy">Workspace</span>
          {navigation.map((item) => {
            const isActive = item.end
              ? currentPath === item.to
              : currentPath.startsWith(item.to);
            const Icon = item.icon;
            return (
              <a
                key={item.to}
                href={item.to}
                className={isActive ? "nav-link active" : "nav-link"}
                title={item.label}
                onClick={() => setMobileOpen(false)}
              >
                <Icon size={18} strokeWidth={1.8} />
                <span className="brand-copy">{item.label}</span>
              </a>
            );
          })}
        </nav>

        <div className="sidebar-context brand-copy">
          <span className="nav-caption">Recent</span>
          <a href="/chat">
            <BookOpenText size={15} />
            Remote policy research
          </a>
          <a href="/video">
            <Sparkles size={15} />
            Transcript insights
          </a>
        </div>

        <div className="model-pulse brand-copy">
          <span className="pulse-orbit" aria-hidden="true" />
          <span>
            <strong>
              {modelConfiguration?.model_warm
                ? "Local models warm"
                : modelConfiguration?.embedding_model_cached &&
                    modelConfiguration.generation_model_cached
                  ? "Local models cached"
                  : modelConfiguration
                    ? "Models load on demand"
                    : modelConfigurationChecked
                      ? "Model status unavailable"
                      : "Checking model cache"}
            </strong>
            <small>
              {modelConfiguration
                ? `${modelConfiguration.model_device.toUpperCase()} · private`
                : modelConfigurationChecked
                  ? "Retrying · private"
                  : "Private · no external API"}
            </small>
          </span>
        </div>

        <div className="sidebar-footer">
          <a className="nav-link" href="/settings" title="Settings">
            <Settings size={18} />
            <span className="brand-copy">Settings</span>
          </a>
          <button
            className="nav-link collapse-control"
            onClick={() => setCollapsed((value) => !value)}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <PanelLeftOpen size={18} /> : <PanelLeftClose size={18} />}
            <span className="brand-copy">Collapse</span>
          </button>
        </div>
      </aside>

      <div className="app-content">
        <header className="topbar">
          <button className="command-trigger" onClick={() => setCommandOpen(true)}>
            <Search size={16} />
            <span>Search knowledge or ask anything</span>
            <kbd>
              <Command size={11} /> K
            </kbd>
          </button>
          <div className="topbar-actions">
            <span className="privacy-chip">
              <span />
              Local & private
            </span>
            <button
              className="icon-button"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              aria-label={`Use ${theme === "light" ? "dark" : "light"} mode`}
            >
              {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
            </button>
            <span className="user-avatar" title="Local user">
              FK
            </span>
          </div>
        </header>
        <main className="page-container">{children}</main>
      </div>

      {commandOpen && (
        <div className="command-overlay" role="dialog" aria-modal="true">
          <button
            className="command-dismiss"
            onClick={() => setCommandOpen(false)}
            aria-label="Close command menu"
          />
          <div className="command-palette">
            <form onSubmit={runCommand}>
              <Search size={20} />
              <input
                name="query"
                placeholder="Ask across your knowledge…"
                autoFocus
                aria-label="Search or ask a question"
              />
              <kbd>Enter</kbd>
            </form>
            <div className="command-hints">
              <a href="/upload">
                <UploadCloud size={17} /> Upload a source
              </a>
              <a href="/chat">
                <Bot size={17} /> Open research chat
              </a>
              <a href="/video">
                <Video size={17} /> Explore video intelligence
              </a>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
