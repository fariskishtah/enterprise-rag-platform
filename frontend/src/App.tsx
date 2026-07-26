import { lazy, Suspense } from "react";

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
  import("./pages/IntelligencePage").then((module) => ({
    default: module.IntelligencePage,
  })),
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

export default function App() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  const documentMatch = path.match(/^\/documents\/([A-Za-z0-9-]+)$/);
  const mediaMatch = path.match(/^\/media\/([A-Za-z0-9-]+)$/);
  const workspaceMatch = path.match(/^\/knowledge-bases\/([A-Za-z0-9-]+)$/);
  const page =
    path === "/" || path === "/dashboard" || path === "/workspace" ? (
      <DashboardPage />
    ) : path === "/landing" ? (
      <LandingPage />
    ) : path === "/evaluation" ? (
      <EvaluationPage />
    ) : path === "/feedback" ? (
      <FeedbackPage />
    ) : path === "/templates" ? (
      <TemplatesPage />
    ) : path === "/login" ? (
      <LoginPage />
    ) : path === "/knowledge-bases" ? (
      <KnowledgeBasesPage />
    ) : path === "/upload" || path === "/documents" ? (
      <UploadPage />
    ) : path === "/chat" ? (
      <ChatPage />
    ) : path === "/intelligence" ? (
      <IntelligencePage />
    ) : path === "/video" || path === "/media" ? (
      <VideoPage />
    ) : path === "/settings" ? (
      <SettingsPage />
    ) : documentMatch?.[1] ? (
      <DocumentPage documentId={documentMatch[1]} />
    ) : mediaMatch?.[1] ? (
      <VideoPage mediaId={mediaMatch[1]} />
    ) : workspaceMatch?.[1] ? (
      <WorkspacePage knowledgeBaseId={workspaceMatch[1]} />
    ) : (
      <section className="empty-state">
        <h1>Page not found</h1>
        <p>The requested workspace page does not exist.</p>
        <a className="button primary" href="/">
          Return to dashboard
        </a>
      </section>
    );

  return (
    <AppShell>
      <Suspense
        fallback={
          <section className="route-loader" aria-label="Loading workspace">
            <span className="skeleton-line" />
            <span className="skeleton-line" />
            <span className="skeleton-line" />
          </section>
        }
      >
        {page}
      </Suspense>
    </AppShell>
  );
}
