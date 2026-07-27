import { ArrowLeft, Github, ShieldCheck } from "lucide-react";

type LegalKind = "privacy" | "terms" | "security";

const content: Record<LegalKind, { title: string; introduction: string; sections: Array<[string, string]> }> = {
  privacy: {
    title: "Privacy notice",
    introduction:
      "This public demo notice is informational and is not legal advice. Do not upload confidential, personal, regulated, or otherwise sensitive information.",
    sections: [
      [
        "Data stored by the demo",
        "Knowledge-base names, uploaded documents and media, extracted text, transcripts, vector indexes, questions, generated answers, citations, and operational metadata are stored on the demo server.",
      ],
      [
        "Retention and deletion",
        "Demo-created data is configured to expire after 24 hours by default. A scheduled cleanup removes expired database records, uploaded files, derived media, and old temporary files. Operational recovery backups may follow a separate seven-day retention schedule.",
      ],
      [
        "Sessions and third parties",
        "An HttpOnly session cookie controls demo access. The application does not need paid AI APIs, but model files may be downloaded from Hugging Face. YouTube import depends on YouTube and yt-dlp availability and may fail from cloud-hosted IP addresses.",
      ],
      [
        "Questions and issues",
        "Report a privacy or reliability concern through the project’s GitHub issue tracker. Do not include private data, credentials, cookie files, or uploaded content in an issue.",
      ],
    ],
  },
  terms: {
    title: "Demo terms",
    introduction:
      "EnterpriseRAG is provided for demonstration and evaluation. This notice is not legal advice and does not create a service-level agreement.",
    sections: [
      [
        "Availability and accuracy",
        "There is no uptime or accuracy guarantee. AI output may contain errors; verify citations and source material before relying on an answer.",
      ],
      [
        "Your responsibilities",
        "Only upload content you are permitted to use. Illegal, abusive, confidential, personal, regulated, or rights-infringing uploads are prohibited.",
      ],
      [
        "Limits and deletion",
        "The demo applies storage, file, duration, rate, and compute limits. Data may be deleted automatically after the configured retention period, and abusive workloads may be rejected or removed.",
      ],
    ],
  },
  security: {
    title: "Implemented security controls",
    introduction:
      "This page describes controls implemented in this repository. It does not claim penetration testing, certification, compliance, or an independent security audit.",
    sections: [
      [
        "Access and request controls",
        "The public-demo mode uses bcrypt password verification, signed expiring HttpOnly sessions, Secure cookie support, same-site protection, login lockout, route protection, rate limits, request-size limits, and request IDs.",
      ],
      [
        "File and compute controls",
        "Uploads use server-generated storage names, path containment, extension and signature validation, size and duration limits, and a bounded shared heavy-operation queue.",
      ],
      [
        "Operations",
        "Cookie secrets are mounted read-only and never logged, backups use SQLite-safe copies and integrity checks, cleanup is path-contained, HTTPS deployment guidance is supplied, and CI installs dependencies and runs lint, test, and build checks.",
      ],
    ],
  },
};

export function LegalPage({ kind }: { kind: LegalKind }) {
  const page = content[kind];
  return (
    <div className="public-page legal-page">
      <nav className="public-nav" aria-label="Public navigation">
        <a className="public-brand" href="/">
          <ShieldCheck size={22} /> EnterpriseRAG
        </a>
        <a className="button secondary" href="/">
          <ArrowLeft size={16} /> Back to overview
        </a>
      </nav>
      <main className="legal-content">
        <span className="eyebrow">Public demo policy</span>
        <h1>{page.title}</h1>
        <p className="legal-intro">{page.introduction}</p>
        {page.sections.map(([title, body]) => (
          <section key={title}>
            <h2>{title}</h2>
            <p>{body}</p>
          </section>
        ))}
      </main>
      <footer className="public-footer">
        <a href="https://github.com/fariskishtah/enterprise-rag-platform" target="_blank" rel="noreferrer">
          <Github size={15} /> GitHub
        </a>
        <a href="/privacy">Privacy</a>
        <a href="/terms">Terms</a>
        <a href="/security">Security</a>
      </footer>
    </div>
  );
}
