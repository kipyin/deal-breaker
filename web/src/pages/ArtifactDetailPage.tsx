import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getArtifact } from "../api/client";
import type { ArtifactDetail } from "../api/types";

export function ArtifactDetailPage() {
  const { artifactId } = useParams<{ artifactId: string }>();
  const [row, setRow] = useState<ArtifactDetail | null>(null);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!artifactId) return;
    let c = false;
    (async () => {
      try {
        const d = await getArtifact(artifactId);
        if (!c) setRow(d);
      } catch (e) {
        if (!c) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      c = true;
    };
  }, [artifactId]);

  if (!artifactId) return <p className="error">Missing artifact id</p>;

  const download = row?.links.download;

  return (
    <section aria-label="Artifact detail" className="game-surface detail-shell detail-arcade">
      <header className="surface-hero">
        <p className="surface-hero__topline">Artifact detail</p>
        <h1 className="page-title">Artifact</h1>
        <p className="detail-nav">
          <Link to="/artifacts">All artifacts</Link>
          {" · "}
          <Link to="/">Cockpit</Link>
        </p>
      </header>
      {err && <p className="error">{err}</p>}
      {!err && row == null && <p className="muted">Loading…</p>}
      {row != null && (
        <section className="panel surface-panel">
          <p className="surface-kicker">Vault record</p>
          <h2>{row.label ?? row.id}</h2>
          <p className="muted">
            <code>{row.id}</code> · <span className="tag">{row.kind}</span>
          </p>
          <dl className="detail-dl">
            <dt>Path</dt>
            <dd>
              <code>{row.path}</code>
            </dd>
            <dt>Created</dt>
            <dd>{row.created_at}</dd>
            {row.imported_at && (
              <>
                <dt>Imported</dt>
                <dd>{row.imported_at}</dd>
              </>
            )}
            {row.job_id && (
              <>
                <dt>Job</dt>
                <dd>
                  <Link to={`/jobs/${row.job_id}`}>{row.job_id}</Link>
                </dd>
              </>
            )}
            {row.checkpoint_id && (
              <>
                <dt>Checkpoint</dt>
                <dd>
                  <Link to={`/checkpoints/${row.checkpoint_id}`}>
                    {row.checkpoint_id}
                  </Link>
                </dd>
              </>
            )}
          </dl>
          <div className="row" style={{ marginTop: "0.75rem" }}>
            {download && (
              <a className="pixel-button" href={download}>
                Download file
              </a>
            )}
          </div>
          <h3 style={{ marginTop: "1rem", fontSize: "0.95rem" }}>Metadata</h3>
          <pre className="inspector-raw">
            {JSON.stringify(row.metadata, null, 2)}
          </pre>
        </section>
      )}
    </section>
  );
}
