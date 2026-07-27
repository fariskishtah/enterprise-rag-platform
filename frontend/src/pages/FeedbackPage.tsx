import { useEffect, useState } from "react";
import { getFeedbackAnalytics } from "../api/client";

interface AnalyticsData {
  total_feedback: number;
  helpful_count: number;
  unhelpful_count: number;
  helpful_rate: number;
  complaint_categories: Record<string, number>;
}

export function FeedbackPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    getFeedbackAnalytics()
      .then((data) => {
        if (active) setAnalytics(data);
      })
      .catch((err: unknown) => {
        if (active) {
          setError(err instanceof Error ? err.message : "Unable to load feedback analytics.");
        }
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <section className="feedback-page">
      <div className="page-header">
        <div>
          <span className="eyebrow">User Satisfaction</span>
          <h1>Feedback Analytics</h1>
          <p>Review aggregate helpfulness ratings and complaint categories captured by the feedback API.</p>
        </div>
      </div>

      {error && <div className="notice error" role="alert">{error}</div>}
      {loading && <div className="panel loading-state">Loading feedback analytics…</div>}

      {/* Analytics Cards */}
      <div className="metrics-banner" aria-busy={loading}>
        <div className="metric-card">
          <span className="metric-label">Helpful Rate</span>
          <strong className="metric-value">
            {analytics && analytics.total_feedback > 0
              ? `${(analytics.helpful_rate * 100).toFixed(0)}%`
              : "No data"}
          </strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Total Submissions</span>
          <strong className="metric-value">{analytics?.total_feedback ?? "—"}</strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Positive Feedback</span>
          <strong className="metric-value">{analytics?.helpful_count ?? "—"}</strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Complaints Recorded</span>
          <strong className="metric-value">{analytics?.unhelpful_count ?? "—"}</strong>
        </div>
      </div>

      {/* Complaint Categories Breakdown */}
      <article className="panel">
        <h2>Complaint Category Breakdown</h2>
        <div className="category-breakdown-list">
          {Object.entries(analytics?.complaint_categories ?? {}).length === 0 ? (
            <p className="muted-copy">No unhelpful feedback complaints recorded yet.</p>
          ) : (
            Object.entries(analytics?.complaint_categories ?? {}).map(([cat, count]) => (
              <div key={cat} className="category-row">
                <span className="category-name">{cat.replaceAll("_", " ")}</span>
                <span className="category-count">{count} cases</span>
              </div>
            ))
          )}
        </div>
      </article>
    </section>
  );
}
