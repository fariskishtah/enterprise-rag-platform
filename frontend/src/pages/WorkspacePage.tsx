import {
  BarChart3,
  Bot,
  FileStack,
  Files,
  FlaskConical,
  LayoutDashboard,
  Settings,
  Sparkles,
} from "lucide-react";

const tabs = [
  ["Overview", LayoutDashboard, "/dashboard", false],
  ["Sources", FileStack, "/upload", true],
  ["Chat", Bot, "/chat", true],
  ["Summaries", Sparkles, "/intelligence", true],
  ["Compare", Files, "/intelligence", true],
  ["Reports", BarChart3, "/intelligence", true],
  ["Evaluation", FlaskConical, "/evaluation", false],
  ["Settings", Settings, "/settings", false],
] as const;

export function WorkspacePage({ knowledgeBaseId }: { knowledgeBaseId: string }) {
  return (
    <section className="workspace-page">
      <header>
        <span className="eyebrow">Knowledge workspace</span>
        <h1>Focused collection</h1>
        <p>One source boundary, every intelligence workflow.</p>
      </header>
      <nav className="workspace-tabs" aria-label="Knowledge base sections">
        {tabs.map(([label, Icon, target, preservesScope]) => (
          <a
            key={label}
            href={
              preservesScope
                ? `${target}?knowledgeBase=${encodeURIComponent(knowledgeBaseId)}`
                : target
            }
          >
            <Icon size={17} />
            {label}
          </a>
        ))}
      </nav>
      <div className="workspace-landing">
        <span><Sparkles size={28} /></span>
        <h2>Choose a workflow above.</h2>
        <p>
          Source, chat, and intelligence shortcuts preserve this collection selection.
          Overview, evaluation, and settings open shared workspace views.
        </p>
      </div>
    </section>
  );
}
