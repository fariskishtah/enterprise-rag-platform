import {
  ArrowRight,
  Bot,
  FileCheck2,
  FileText,
  Github,
  Globe2,
  Headphones,
  LockKeyhole,
  MessageSquareQuote,
  ShieldAlert,
  Sparkles,
} from "lucide-react";

const repository = "https://github.com/fariskishtah/enterprise-rag-platform";

export function LandingPage() {
  return (
    <div className="public-page landing-page">
      <nav className="public-nav" aria-label="Public navigation">
        <a className="public-brand" href="/">
          <Sparkles size={22} /> EnterpriseRAG
        </a>
        <div>
          <a href="#workflow">How it works</a>
          <a href="#limitations">Limitations</a>
          <a className="button primary" href="/login">Try the demo</a>
        </div>
      </nav>

      <main>
        <header className="landing-hero">
          <div className="landing-hero-content">
            <span className="eyebrow">Local-first multilingual knowledge intelligence</span>
            <h1>Ask your sources. See the evidence.</h1>
            <p>
              Upload documents or media, ask grounded questions in Arabic or English,
              and inspect citations, transcripts, summaries, and intelligence outputs—on
              an architecture designed to run privately on your own infrastructure.
            </p>
            <div className="landing-cta-group">
              <a className="button primary large" href="/login">
                Try the demo <ArrowRight size={18} />
              </a>
              <a className="button secondary large" href={repository} target="_blank" rel="noreferrer">
                <Github size={18} /> View GitHub
              </a>
              <a className="button tertiary large" href={`${repository}#readme`} target="_blank" rel="noreferrer">
                Read documentation
              </a>
            </div>
          </div>
          <aside className="hero-evidence" aria-label="Example grounded answer">
            <span className="hero-evidence-label"><Bot size={16} /> Grounded answer</span>
            <blockquote dir="rtl" lang="ar">تسمح السياسة بالعمل عن بُعد حتى ثلاثة أيام أسبوعياً.</blockquote>
            <div><FileCheck2 size={17} /> Policy.pdf · page 4 · citation verified</div>
          </aside>
        </header>

        <section className="demo-warning" aria-labelledby="demo-warning-title">
          <ShieldAlert size={24} />
          <div>
            <h2 id="demo-warning-title">This is a public evaluation environment</h2>
            <p>
              Do not upload confidential, personal, or regulated information. Demo files
              may be deleted automatically. AI output can be wrong—check every citation.
              YouTube import is best-effort; direct MP3 or MP4 upload is more reliable.
            </p>
          </div>
        </section>

        <section className="landing-features" aria-label="Product capabilities">
          <article className="feature-card">
            <FileText className="feature-icon" />
            <h2>Document intelligence</h2>
            <p>Validate, extract, chunk, and search PDF, DOCX, and UTF-8 text sources.</p>
          </article>
          <article className="feature-card">
            <MessageSquareQuote className="feature-icon" />
            <h2>Grounded answers</h2>
            <p>Trace responses to source passages, page references, and timestamp citations.</p>
          </article>
          <article className="feature-card">
            <Globe2 className="feature-icon" />
            <h2>Arabic and English</h2>
            <p>Use multilingual retrieval, language-aware prompts, and right-to-left output.</p>
          </article>
          <article className="feature-card">
            <Headphones className="feature-icon" />
            <h2>Audio and video</h2>
            <p>Transcribe direct media uploads, search timestamps, and generate local summaries.</p>
          </article>
          <article className="feature-card">
            <Sparkles className="feature-icon" />
            <h2>Intelligence tools</h2>
            <p>Create evidence-based summaries, comparisons, reports, and media insights.</p>
          </article>
          <article className="feature-card">
            <LockKeyhole className="feature-icon" />
            <h2>Deploy it locally</h2>
            <p>Run React, FastAPI, SQLite, Hugging Face models, and storage in your environment.</p>
          </article>
        </section>

        <section className="workflow-section" id="workflow">
          <span className="eyebrow">Simple workflow</span>
          <h2>From source to supported answer</h2>
          <ol className="workflow-grid">
            <li><strong>01</strong><h3>Add knowledge</h3><p>Upload a supported document, MP3, or MP4.</p></li>
            <li><strong>02</strong><h3>Process locally</h3><p>Extract text or transcribe speech, then build the retrieval index.</p></li>
            <li><strong>03</strong><h3>Ask and inspect</h3><p>Review the answer, supporting passage, page, or timestamp.</p></li>
          </ol>
        </section>

        <section className="limitations-section" id="limitations">
          <div>
            <span className="eyebrow">Honest constraints</span>
            <h2>Designed for a focused CPU demo</h2>
          </div>
          <ul>
            <li>CPU generation can take time and only one heavy request runs at once.</li>
            <li>Public-demo storage, duration, request, and rate quotas apply.</li>
            <li>Unsupported questions should return an insufficient-evidence response.</li>
            <li>YouTube may reject cloud-hosted IP addresses; direct upload is the fallback.</li>
          </ul>
        </section>
      </main>

      <footer className="public-footer">
        <span>EnterpriseRAG public demo</span>
        <a href={repository} target="_blank" rel="noreferrer">GitHub</a>
        <a href={`${repository}#readme`} target="_blank" rel="noreferrer">Documentation</a>
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms / demo notice</a>
        <a href="/security">Security</a>
      </footer>
    </div>
  );
}
