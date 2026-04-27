import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getEvaluation } from "../api/client";
import type { EvaluationDetail } from "../api/types";

export function EvaluationDetailPage() {
  const { evaluationId } = useParams<{ evaluationId: string }>();
  const [row, setRow] = useState<EvaluationDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!evaluationId) return;
    let c = false;
    (async () => {
      try {
        const d = await getEvaluation(evaluationId);
        if (!c) setRow(d);
      } catch (e) {
        if (!c) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      c = true;
    };
  }, [evaluationId]);

  if (!evaluationId) return <p className="error">Missing evaluation id</p>;

  return (
    <section aria-label="Evaluation detail" className="game-surface detail-shell detail-arcade">
      <header className="surface-hero">
        <p className="surface-hero__topline">Evaluation detail</p>
        <h1 className="page-title">Evaluation</h1>
        <p className="detail-nav">
          <Link to="/evaluate">Evaluation lab</Link>
          {" · "}
          <Link to="/">Cockpit</Link>
        </p>
      </header>
      {err && <p className="error">{err}</p>}
      {!err && row == null && <p className="muted">Loading…</p>}
      {row != null && (
        <>
          <section className="panel surface-panel">
            <p className="surface-kicker">Match report</p>
            <h2>Summary</h2>
            <p className="muted">
              <code>{row.id}</code>
              {row.job_id && (
                <>
                  {" · "}
                  <Link to={`/jobs/${row.job_id}`}>job {row.job_id}</Link>
                </>
              )}
            </p>
            <dl className="detail-dl">
              <dt>Candidate</dt>
              <dd>
                <code>{row.candidate}</code>
              </dd>
              <dt>Players</dt>
              <dd>{row.player_count}</dd>
              <dt>Games</dt>
              <dd>{row.games}</dd>
              <dt>Seed</dt>
              <dd>{row.seed}</dd>
              <dt>Baselines</dt>
              <dd>{row.baselines.join(", ")}</dd>
              <dt>Candidate score</dt>
              <dd>{row.candidate_score.toFixed(4)}</dd>
              <dt>Promotion</dt>
              <dd>
                {row.promoted === true && (
                  <span className="tag tag--promoted">Promoted</span>
                )}
                {row.promoted === false && (
                  <span className="tag tag--muted">Not promoted</span>
                )}
                {row.promoted == null && "—"}
                {row.promotion_reason && (
                  <span className="muted"> — {row.promotion_reason}</span>
                )}
              </dd>
            </dl>
          </section>

          <section className="panel surface-panel">
            <p className="surface-kicker">Leaderboard</p>
            <h2>Strategy scores</h2>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Strategy</th>
                  <th>Score</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(row.strategy_scores)
                  .sort((a, b) => b[1] - a[1])
                  .map(([name, score]) => (
                    <tr key={name}>
                      <td>
                        <code>{name}</code>
                      </td>
                      <td>{score.toFixed(4)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </section>

          <section className="panel surface-panel">
            <p className="surface-kicker">Raw report</p>
            <h2>Report</h2>
            <pre className="inspector-raw">
              {JSON.stringify(row.report, null, 2)}
            </pre>
          </section>
        </>
      )}
    </section>
  );
}
