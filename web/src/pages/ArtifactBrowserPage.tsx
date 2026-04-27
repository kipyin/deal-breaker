import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { listArtifacts } from "../api/client";
import type { ArtifactListItem } from "../api/types";

const KIND_OPTIONS: { value: string; label: string }[] = [
  { value: "", label: "All kinds" },
  { value: "checkpoint", label: "checkpoint" },
  { value: "manifest", label: "manifest" },
  { value: "evaluation_report", label: "evaluation_report" },
  { value: "tournament_report", label: "tournament_report" },
];

export function ArtifactBrowserPage() {
  const [artifacts, setArtifacts] = useState<ArtifactListItem[]>([]);
  const [kind, setKind] = useState("");
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const response = await listArtifacts({
          limit: 40,
          kind: kind || undefined,
        });
        if (!cancelled) setArtifacts(response.items);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [kind]);

  return (
    <section aria-label="Artifact vault" className="game-surface page-console archive-console">
      <header className="surface-hero">
        <p className="surface-hero__topline">Artifact vault</p>
        <h1 className="page-title">Artifacts</h1>
        <p className="surface-hero__copy">
          Browse indexed files under the artifact root. Open a row for metadata
          and related jobs or checkpoints.
        </p>
      </header>
      {err && <p className="error">{err}</p>}
      <section className="panel surface-panel">
        <div className="row" style={{ marginBottom: "0.75rem" }}>
          <label>
            Kind{" "}
            <select
              value={kind}
              onChange={(e) => setKind(e.target.value)}
            >
              {KIND_OPTIONS.map((o) => (
                <option key={o.value || "all"} value={o.value}>
                  {o.label}
                </option>
              ))}
            </select>
          </label>
        </div>
        <p className="surface-kicker">Indexed cache</p>
        <h2>Indexed artifacts</h2>
        {artifacts.length === 0 && (
          <p className="muted">No artifacts for this filter.</p>
        )}
        {artifacts.map((artifact) => (
          <div className="job-item" key={artifact.id}>
            <Link to={`/artifacts/${artifact.id}`}>
              {artifact.label ?? artifact.id}
            </Link>{" "}
            <span className="muted">
              <span className="tag">{artifact.kind}</span> · {artifact.path}
            </span>
            {artifact.links.download && (
              <>
                {" "}
                <a href={artifact.links.download}>Download</a>
              </>
            )}
          </div>
        ))}
      </section>
    </section>
  );
}
