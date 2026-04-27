import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { getCheckpoint } from "../api/client";
import type { CheckpointDetail } from "../api/types";

function neuralSpecForPath(relPath: string): string {
  return `neural:${relPath}`;
}

export function CheckpointDetailPage() {
  const { checkpointId } = useParams<{ checkpointId: string }>();
  const navigate = useNavigate();
  const [cp, setCp] = useState<CheckpointDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const neuralSpec = useMemo(
    () => (cp ? neuralSpecForPath(cp.path) : ""),
    [cp]
  );

  useEffect(() => {
    if (!checkpointId) return;
    let c = false;
    (async () => {
      try {
        const row = await getCheckpoint(checkpointId);
        if (!c) setCp(row);
      } catch (e) {
        if (!c) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      c = true;
    };
  }, [checkpointId]);

  if (!checkpointId) return <p className="error">Missing checkpoint id</p>;

  function openPromotionEval() {
    const q = new URLSearchParams();
    q.set("candidate", neuralSpec);
    q.set("promote", "1");
    navigate(`/evaluate?${q.toString()}`);
  }

  return (
    <section aria-label="Checkpoint detail" className="game-surface detail-shell detail-arcade">
      <header className="surface-hero">
        <p className="surface-hero__topline">Checkpoint detail</p>
        <h1 className="page-title">Checkpoint</h1>
        <p className="detail-nav">
          <Link to="/">Cockpit</Link>
          {" · "}
          <Link to="/train">Training lab</Link>
        </p>
      </header>
      {err && <p className="error">{err}</p>}
      {!err && cp == null && <p className="muted">Loading…</p>}
      {cp != null && (
        <>
          <section className="panel surface-panel">
            <p className="surface-kicker">Strategy card</p>
            <h2>{cp.label ?? cp.id}</h2>
            <p className="muted">
              <code>{cp.id}</code>
              {cp.promoted ? (
                <>
                  {" "}
                  <span className="tag tag--promoted">promoted</span>
                </>
              ) : null}
            </p>
            <dl className="detail-dl">
              <dt>Strategy</dt>
              <dd>
                <code>{cp.strategy_spec}</code>
              </dd>
              <dt>Artifact path</dt>
              <dd>
                <code>{cp.path}</code>
              </dd>
              <dt>Players</dt>
              <dd>{cp.player_count ?? "—"}</dd>
              <dt>Neural spec (for jobs)</dt>
              <dd>
                <code>{neuralSpec}</code>
              </dd>
              {cp.source_job_id && (
                <>
                  <dt>Source job</dt>
                  <dd>
                    <Link to={`/jobs/${cp.source_job_id}`}>
                      {cp.source_job_id}
                    </Link>
                  </dd>
                </>
              )}
              {cp.manifest_path && (
                <>
                  <dt>Manifest</dt>
                  <dd>
                    <code>{cp.manifest_path}</code>
                  </dd>
                </>
              )}
            </dl>
            <div className="row" style={{ marginTop: "0.75rem" }}>
              <button
                className="pixel-button"
                type="button"
                onClick={() => openPromotionEval()}
                disabled={!neuralSpec.startsWith("neural:")}
              >
                Evaluate with promotion
              </button>
              <span className="muted">
                Opens the evaluation lab with this candidate and{" "}
                <em>Promote if passes</em> enabled. Set the champions manifest
                path before starting.
              </span>
            </div>
          </section>
          <section className="panel surface-panel">
            <p className="surface-kicker">Training telemetry</p>
            <h2>Training stats</h2>
            <pre className="inspector-raw">
              {JSON.stringify(cp.training_stats, null, 2)}
            </pre>
          </section>
        </>
      )}
    </section>
  );
}
