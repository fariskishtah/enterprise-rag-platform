import { AlertTriangle } from "lucide-react";
import { Component, type ErrorInfo, type ReactNode } from "react";

interface State {
  error: Error | null;
}

export class ErrorBoundary extends Component<{ children: ReactNode }, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("EnterpriseRAG interface failure", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <main className="fatal-error">
          <AlertTriangle size={28} />
          <span className="eyebrow">Interface recovery</span>
          <h1>This workspace view could not be rendered.</h1>
          <p>{this.state.error.message}</p>
          <button className="button primary" onClick={() => window.location.reload()}>
            Reload workspace
          </button>
        </main>
      );
    }
    return this.props.children;
  }
}
