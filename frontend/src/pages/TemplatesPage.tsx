import { useEffect, useState } from "react";
import {
  AlertTriangle,
  BookOpen,
  Calendar,
  CheckSquare,
  FileText,
  GitCompare,
  Grid,
  HelpCircle,
  List,
  Play,
  ShieldCheck,
  UserCheck,
  Video,
} from "lucide-react";
import { listTemplates } from "../api/client";

interface Template {
  id: string;
  title: string;
  description: string;
  category: string;
  prompt_instruction: string;
  supported_source_types: string[];
  output_schema_type: string;
  safety_classification: string;
  icon_name: string;
}

export function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [selectedCategory, setSelectedCategory] = useState<string>("All");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    listTemplates()
      .then(setTemplates)
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Unable to load action templates.");
      });
  }, []);

  const categories = ["All", ...Array.from(new Set(templates.map((t) => t.category)))];

  const filteredTemplates =
    selectedCategory === "All"
      ? templates
      : templates.filter((t) => t.category === selectedCategory);

  return (
    <section className="templates-page">
      <div className="page-header">
        <div>
          <span className="eyebrow">Enterprise Workflows</span>
          <h1>Action Template Library</h1>
          <p>Pre-configured, evidence-backed AI action templates for contracts, HR, meetings, and study notes.</p>
        </div>
      </div>

      {error && <div className="notice error">{error}</div>}

      {/* Category Tabs */}
      <div className="mode-tabs" role="tablist">
        {categories.map((cat) => (
          <button
            key={cat}
            className={selectedCategory === cat ? "mode-tab active" : "mode-tab"}
            onClick={() => setSelectedCategory(cat)}
          >
            {cat}
          </button>
        ))}
      </div>

      {/* Template Grid */}
      <div className="templates-grid">
        {filteredTemplates.map((template) => (
          <div key={template.id} className="template-card">
            <div className="template-card-header">
              <span className="badge category-badge">{template.category}</span>
              <span className="badge safety-badge">{template.safety_classification}</span>
            </div>
            <h3>{template.title}</h3>
            <p>{template.description}</p>
            <div className="template-card-footer">
              <a
                className="button primary small"
                href={`/chat?question=${encodeURIComponent(template.prompt_instruction)}`}
              >
                <Play size={14} /> Run Workflow
              </a>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
