import { lazy, type ReactNode, Suspense, useEffect, useState } from "react";

import { getAuthSession } from "./api/client";
import { AppShell } from "./components/AppShell";

const ChatPage = lazy(() =>
  import("./pages/ChatPage").then((module) => ({ default: module.ChatPage })),
);
const DashboardPage = lazy(() =>
  import("./pages/DashboardPage").then((module) => ({ default: module.DashboardPage })),
);
const DocumentPage = lazy(() =>
  import("./pages/DocumentPage").then((module) => ({ default: module.DocumentPage })),
);
const IntelligencePage = lazy(() =>
  import("./pages/IntelligencePage").then((module) => ({ default: module.IntelligencePage })),
);
const KnowledgeBasesPage = lazy(() =>
  import("./pages/KnowledgeBasesPage").then((module) => ({
    default: module.KnowledgeBasesPage,
  })),
);
const SettingsPage = lazy(() =>
  import("./pages/SettingsPage").then((module) => ({ default: module.SettingsPage })),
);
const UploadPage = lazy(() =>
  import("./pages/UploadPage").then((module) => ({ default: module.UploadPage })),
);
const VideoPage = lazy(() =>
  import("./pages/VideoPage").then((module) => ({ default: module.VideoPage })),
);
const WorkspacePage = lazy(() =>
  import("./pages/WorkspacePage").then((module) => ({ default: module.WorkspacePage })),
);
const LandingPage = lazy(() =>
  import("./pages/LandingPage").then((module) => ({ default: module.LandingPage })),
);
const EvaluationPage = lazy(() =>
  import("./pages/EvaluationPage").then((module) => ({ default: module.EvaluationPage })),
);
const FeedbackPage = lazy(() =>
  import("./pages/FeedbackPage").then((module) => ({ default: module.FeedbackPage })),
);
const TemplatesPage = lazy(() =>
  import("./pages/TemplatesPage").then((module) => ({ default: module.TemplatesPage })),
);
const LoginPage = lazy(() =>
  import("./pages/LoginPage").then((module) => ({ default: module.LoginPage })),
);
const LegalPage = lazy(() =>
  import("./pages/LegalPage").then((module) => ({ default: module.LegalPage })),
);

function RouteLoader() {
  return (
    <section className="route-loader" aria-label="Loading workspace">
      <span className="skeleton-line" />
      <span className="skeleton-line" />
      <span className="skeleton-line" />
    </section>
  );
}

function Authenticated({ children }: { children: ReactNode }) {
  const [state, setState] = useState<"checking" | "allowed" | "denied">("checking");

  useEffect(() => {
    let active = true;
    const verify = () => {
      getAuthSession()
        .then((session) => {
          if (!active) return;
          setState(session.authenticated ? "allowed" : "denied");
          if (!session.authenticated) {
            const next = `${window.location.pathname}${window.location.search}`;
            window.location.assign(`/login?next=${encodeURIComponent(next)}`);
          }
        })
        .catch(() => {
          if (!active) return;
          setState("denied");
          const next = `${window.location.pathname}${window.location.search}`;
          window.location.assign(`/login?next=${encodeURIComponent(next)}`);
        });
    };
    const unauthorized = () => {
      if (!active) return;
      setState("denied");
      const next = `${window.location.pathname}${window.location.search}`;
      window.location.assign(`/login?next=${encodeURIComponent(next)}`);
    };
    verify();
    window.addEventListener("enterprise-rag:unauthorized", unauthorized);
    return () => {
      active = false;
      window.removeEventListener("enterprise-rag:unauthorized", unauthorized);
    };
  }, []);

  if (state !== "allowed") {
    return (
      <main className="auth-check" aria-live="polite">
        {state === "checking" ? "Checking demo access…" : "Redirecting to sign in…"}
      </main>
    );
  }
  return <AppShell>{children}</AppShell>;
}

export default function App() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  const documentMatch = path.match(/^\/documents\/([A-Za-z0-9-]+)$/);
  const mediaMatch = path.match(/^\/media\/([A-Za-z0-9-]+)$/);
  const workspaceMatch = path.match(/^\/knowledge-bases\/([A-Za-z0-9-]+)$/);

  let page: ReactNode;
  let isPublic = false;
  if (path === "/" || path === "/landing") {
    isPublic = true;
    page = <LandingPage />;
  } else if (path === "/login") {
    isPublic = true;
    page = <LoginPage />;
  } else if (path === "/privacy" || path === "/terms" || path === "/security") {
    isPublic = true;
    page = <LegalPage kind={path.slice(1) as "privacy" | "terms" | "security"} />;
  } else if (path === "/dashboard" || path === "/workspace") {
    page = <DashboardPage />;
  } else if (path === "/evaluation") {
    page = <EvaluationPage />;
  } else if (path === "/feedback") {
    page = <FeedbackPage />;
  } else if (path === "/templates") {
    page = <TemplatesPage />;
  } else if (path === "/knowledge-bases") {
    page = <KnowledgeBasesPage />;
  } else if (path === "/upload" || path === "/documents") {
    page = <UploadPage />;
  } else if (path === "/chat") {
    page = <ChatPage />;
  } else if (path === "/intelligence") {
    page = <IntelligencePage />;
  } else if (path === "/video" || path === "/media") {
    page = <VideoPage />;
  } else if (path === "/settings") {
    page = <SettingsPage />;
  } else if (documentMatch?.[1]) {
    page = <DocumentPage documentId={documentMatch[1]} />;
  } else if (mediaMatch?.[1]) {
    page = <VideoPage mediaId={mediaMatch[1]} />;
  } else if (workspaceMatch?.[1]) {
    page = <WorkspacePage knowledgeBaseId={workspaceMatch[1]} />;
  } else {
    page = (
      <section className="empty-state">
        <h1>Page not found</h1>
        <p>The requested workspace page does not exist.</p>
        <a className="button primary" href="/dashboard">Return to dashboard</a>
      </section>
    );
  }

  const content = <Suspense fallback={<RouteLoader />}>{page}</Suspense>;
  return isPublic ? content : <Authenticated>{content}</Authenticated>;
}
