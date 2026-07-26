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

export default function App() {
  const path = window.location.pathname.replace(/\/$/, "") || "/";
  const documentMatch = path.match(/^\/documents\/([A-Za-z0-9-]+)$/);
  const mediaMatch = path.match(/^\/media\/([A-Za-z0-9-]+)$/);
  const workspaceMatch = path.match(/^\/knowledge-bases\/([A-Za-z0-9-]+)$/);
  const page =
    path === "/" ? (
      <DashboardPage />
    ) : path === "/knowledge-bases" ? (
      <KnowledgeBasesPage />
    ) : path === "/upload" ? (
      <UploadPage />
    ) : path === "/chat" ? (
      <ChatPage />
    ) : path === "/intelligence" ? (
      <IntelligencePage />
    ) : path === "/video" ? (
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
