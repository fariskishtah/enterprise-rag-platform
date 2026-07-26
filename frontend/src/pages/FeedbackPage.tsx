import { useEffect, useState } from "react";
import { ThumbsUp, ThumbsDown, MessageSquare, ArrowUpRight } from "lucide-react";
import { getFeedbackAnalytics, listEvaluationDatasets, convertFeedbackToEval } from "../api/client";

interface AnalyticsData {
  total_feedback: number;
  helpful_count: number;
  unhelpful_count: number;
  helpful_rate: number;
  complaint_categories: Record<string, number>;
}

export function FeedbackPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [datasets, setDatasets] = useState<Array<{ id: string; name: string }>>([]);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([getFeedbackAnalytics(), listEvaluationDatasets()])
      .then(([aData, dList]) => {
        setAnalytics(aData);
        setDatasets(dList);
      })
      .catch((err: unknown) => {
        setError(err instanceof Error ? err.message : "Unable to load feedback analytics.");
      });
  }, []);

  return (
    <section className="feedback-page">
      <div className="page-header">
        <div>
          <span className="eyebrow">User Satisfaction</span>
          <h1>Feedback Analytics</h1>
          <p>Analyze helpfulness ratings, user complaints, and convert negative feedback to benchmark test cases.</p>
        </div>
      </div>

      {error && <div className="notice error">{error}</div>}
      {notice && <div className="notice success">{notice}</div>}

      {/* Analytics Cards */}
      <div className="metrics-banner">
        <div className="metric-card">
          <span className="metric-label">Helpful Rate</span>
          <strong className="metric-value">
            {analytics ? `${(analytics.helpful_rate * 100).toFixed(0)}%` : "100%"}
          </strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Total Submissions</span>
          <strong className="metric-value">{analytics?.total_feedback ?? 1}</strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Positive Feedback</span>
          <strong className="metric-value">{analytics?.helpful_count ?? 1}</strong>
        </div>
        <div className="metric-card">
          <span className="metric-label">Complaints Recorded</span>
          <strong className="metric-value">{analytics?.unhelpful_count ?? 0}</strong>
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
