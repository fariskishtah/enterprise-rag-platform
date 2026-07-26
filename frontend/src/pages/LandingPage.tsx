import { useState } from "react";
import {
  ArrowRight,
  Bot,
  BrainCircuit,
  CheckCircle,
  FileText,
  Globe,
  Layers,
  Play,
  ShieldCheck,
  Sparkles,
  Video,
} from "lucide-react";
import { seedDemoWorkspace } from "../api/client";

export function LandingPage() {
  const [seeding, setSeeding] = useState(false);
  const [seededNotice, setSeededNotice] = useState<string | null>(null);
  const [seedError, setSeedError] = useState<string | null>(null);

  async function handleSeedDemo() {
    setSeeding(true);
    setSeedError(null);
    setSeededNotice(null);
    try {
      const res = await seedDemoWorkspace();
      setSeededNotice(res.message);
      setTimeout(() => {
        window.location.href = `/chat?knowledgeBase=${res.knowledge_base_id}`;
      }, 1200);
    } catch (err) {
      setSeedError(
        err instanceof Error
          ? err.message
          : "The demo workspace could not be loaded. Please retry.",
      );
    } finally {
      setSeeding(false);
    }
  }

  return (
    <div className="landing-page">
      {/* Hero Banner */}
      <header className="landing-hero">
        <div className="landing-hero-content">
          <span className="eyebrow">Multimodal AI Platform</span>
          <h1>Enterprise Knowledge Intelligence & Grounded QA</h1>
          <p>
            Zero-hallucination research across documents, scanned PDFs, audio, video, and web sources.
            Built with local models, passage verification, and interactive timestamp citations.
          </p>

          <div className="landing-cta-group">
            <button
              className="button primary large"
              onClick={handleSeedDemo}
              disabled={seeding}
            >
              <Sparkles size={18} />
              {seeding ? "Loading Demo Workspace..." : "Load Demo Workspace"}
            </button>
            <a className="button secondary large" href="/chat">
              <Play size={18} />
              Launch Workspace
            </a>
            <a
              className="button tertiary large"
              href="https://github.com/fariskishtah/enterprise-rag-platform"
              target="_blank"
              rel="noreferrer"
            >
              GitHub Repository
            </a>
          </div>

          {seededNotice && <div className="notice success">{seededNotice}</div>}
          {seedError && <div className="notice error">{seedError}</div>}
        </div>
      </header>

      {/* Feature Grid */}
      <section className="landing-features">
        <div className="feature-card">
          <FileText className="feature-icon" />
          <h3>Document Intelligence</h3>
          <p>Extract, chunk, and index PDF, DOCX, and TXT files with sentence-boundary awareness and metadata preservation.</p>
        </div>

        <div className="feature-card">
          <Video className="feature-icon" />
          <h3>Video & Media Intelligence</h3>
          <p>Automatic Whisper transcription, timestamp segment alignment, and synchronized video player jumping.</p>
        </div>

        <div className="feature-card">
          <ShieldCheck className="feature-icon" />
          <h3>Verifiable Citations</h3>
          <p>Sentence-level claim verification checks every answer against source passages to guarantee zero hallucinations.</p>
        </div>

        <div className="feature-card">
          <Globe className="feature-icon" />
          <h3>Arabic & Multilingual QA</h3>
          <p>First-class Modern Standard Arabic support, RTL interface rendering, and multilingual embedding search.</p>
        </div>

        <div className="feature-card">
          <Layers className="feature-icon" />
          <h3>Dual RAG Engines</h3>
          <p>Switch dynamically between Custom Hybrid RAG (Dense + BM25 + Reranker) and LangChain/LCEL course engine.</p>
        </div>

        <div className="feature-card">
          <BrainCircuit className="feature-icon" />
          <h3>Evaluation & Feedback</h3>
          <p>Integrated correctness, faithfulness, and latency dashboard with feedback analytics and case conversion.</p>
        </div>
      </section>
    </div>
  );
}
