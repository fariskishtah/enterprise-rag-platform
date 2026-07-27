import { type FormEvent, useEffect, useState } from "react";
import { ArrowLeft, Lock, Mail, Shield, User } from "lucide-react";
import {
  getAccessConfiguration,
  getAuthSession,
  loginDemo,
  loginUser,
  registerUser,
  type AccessConfiguration,
} from "../api/client";

function safeNextPath(): string {
  const value = new URLSearchParams(window.location.search).get("next") ?? "/dashboard";
  return value.startsWith("/") && !value.startsWith("//") && value.split("?", 1)[0] !== "/login"
    ? value
    : "/dashboard";
}

export function LoginPage() {
  const [mode, setMode] = useState<AccessConfiguration["mode"] | null>(null);
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    Promise.all([getAccessConfiguration(), getAuthSession()])
      .then(([configuration, session]) => {
        if (!active) return;
        setMode(configuration.mode);
        if (session.authenticated && configuration.mode !== "open") {
          window.location.assign(safeNextPath());
        }
      })
      .catch(() => {
        if (active) setError("The access service is unavailable. Please retry shortly.");
      });
    return () => {
      active = false;
    };
  }, []);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!mode) return;
    setLoading(true);
    setError(null);
    setNotice(null);

    try {
      if (mode === "demo_password") {
        await loginDemo(password);
      } else if (mode === "accounts" && isRegister) {
        await registerUser({ email, password, full_name: fullName });
        setNotice("Registration succeeded. Creating your secure session…");
        const result = await loginUser({ email, password });
        window.localStorage.setItem("token", result.access_token);
      } else if (mode === "accounts") {
        const result = await loginUser({ email, password });
        window.localStorage.setItem("token", result.access_token);
      }
      window.location.assign(safeNextPath());
    } catch (reason) {
      window.localStorage.removeItem("token");
      setError(
        reason instanceof Error
          ? reason.message
          : "Authentication failed. Check your details and retry.",
      );
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="auth-page">
      <a className="auth-back" href="/"><ArrowLeft size={16} /> Product overview</a>
      <section className="auth-card">
        <div className="auth-header">
          <Shield size={32} className="auth-icon" />
          <span className="eyebrow">Protected public demo</span>
          <h1>
            {mode === "demo_password"
              ? "Enter the demo"
              : isRegister
                ? "Create account"
                : "Sign in to EnterpriseRAG"}
          </h1>
          <p>
            {mode === "demo_password"
              ? "Use the shared evaluation password supplied by the demo owner."
              : "Sessions expire automatically and application data is subject to demo retention."}
          </p>
        </div>

        {error && <div className="notice error" role="alert">{error}</div>}
        {notice && <div className="notice success">{notice}</div>}

        {mode === "open" ? (
          <a className="button primary large" href={safeNextPath()}>Continue to workspace</a>
        ) : (
          <form onSubmit={handleSubmit} className="auth-form">
            {mode === "accounts" && isRegister && (
              <label>
                Full Name
                <span><User size={16} /><input type="text" value={fullName} onChange={(event) => setFullName(event.target.value)} required /></span>
              </label>
            )}
            {mode === "accounts" && (
              <label>
                Email Address
                <span><Mail size={16} /><input type="email" value={email} onChange={(event) => setEmail(event.target.value)} autoComplete="email" required /></span>
              </label>
            )}
            <label>
              {mode === "demo_password" ? "Demo password" : "Password"}
              <span><Lock size={16} /><input type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="current-password" required /></span>
            </label>
            <button type="submit" className="button primary large" disabled={loading || !mode}>
              {loading ? "Authenticating…" : isRegister ? "Register" : "Sign in"}
            </button>
          </form>
        )}

        {mode === "accounts" && (
          <button
            type="button"
            className="text-button"
            onClick={() => {
              setIsRegister((value) => !value);
              setError(null);
              setNotice(null);
            }}
          >
            {isRegister ? "Already have an account? Sign in" : "Need an account? Register here"}
          </button>
        )}
        <p className="auth-safety">Do not upload confidential, personal, or regulated information.</p>
      </section>
    </main>
  );
}
