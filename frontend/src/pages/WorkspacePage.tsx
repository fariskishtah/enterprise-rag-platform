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
  ["Overview", LayoutDashboard, "/"],
  ["Sources", FileStack, "/upload"],
  ["Chat", Bot, "/chat"],
  ["Summaries", Sparkles, "/intelligence"],
  ["Compare", Files, "/intelligence"],
  ["Reports", BarChart3, "/intelligence"],
  ["Evaluation", FlaskConical, "/intelligence"],
  ["Settings", Settings, "/settings"],
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
        {tabs.map(([label, Icon, target]) => (
          <a
            key={label}
            href={`${target}${target.includes("?") ? "&" : "?"}knowledgeBase=${knowledgeBaseId}`}
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
          Every tab stays scoped to this knowledge base, keeping retrieval and
          comparison boundaries explicit.
        </p>
      </div>
    </section>
  );
}
