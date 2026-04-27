import { Fragment, useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getJob, getJobLogs } from "../api/client";
import type { JobDetail, JsonObject, LogSliceResponse } from "../api/types";

const active = new Set(["queued", "running"]);

const TRAINING_SUMMARY_KEYS: readonly [string, string][] = [
  ["games", "Games"],
  ["steps", "Learner steps"],
  ["mean_reward", "Mean reward (per decision)"],
  ["policy_loss", "Policy loss"],
  ["value_loss", "Value loss"],
  ["total_loss", "Total loss"],
  ["clip_fraction", "Clip fraction"],
  ["mean_entropy", "Mean entropy"],
  ["rollout_seconds", "Rollout time (s)"],
  ["ppo_update_seconds", "PPO update time (s)"],
  ["total_seconds", "Wall time (s)"],
  ["mean_legal_actions_per_step", "Mean legal actions / step"],
  ["learner_steps_mean", "Steps / game (mean)"],
  ["learner_steps_max", "Steps / game (max)"],
  ["mean_reward_per_game_min", "Mean reward / game (min)"],
  ["mean_reward_per_game_max", "Mean reward / game (max)"],
];

function readTrainingMetrics(
  result: JsonObject | null,
): Record<string, unknown> | null {
  if (!result) return null;
  const training = result["training"];
  if (
    !training ||
    typeof training !== "object" ||
    Array.isArray(training)
  ) {
    return null;
  }
  return training as Record<string, unknown>;
}

function formatMetricValue(value: unknown): string {
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return String(value);
    return Number.isInteger(value) ? String(value) : value.toFixed(4);
  }
  if (typeof value === "string") return value;
  return JSON.stringify(value);
}

function backLinkForKind(kind: string): { to: string; label: string } {
  switch (kind) {
    case "evaluation":
      return { to: "/evaluate", label: "Evaluation lab" };
    case "training":
    case "rl_search":
    case "artifact_import":
      return { to: "/train", label: "Training lab" };
    case "tournament":
      return { to: "/evaluate", label: "Evaluation lab" };
    default:
      return { to: "/", label: "Cockpit" };
  }
}

export function JobDetailPage() {
  const { jobId } = useParams<{ jobId: string }>();
  const [job, setJob] = useState<JobDetail | null>(null);
  const [logs, setLogs] = useState<LogSliceResponse | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const refreshJob = useCallback(async () => {
    if (!jobId) return;
    try {
      const response = await getJob(jobId);
      setJob(response);
      setErr(null);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [jobId]);

  const refreshLogs = useCallback(async () => {
    if (!jobId) return;
    try {
      const slice = await getJobLogs(jobId, { offset: 0, limit: 400 });
      setLogs(slice);
    } catch {
      setLogs(null);
    }
  }, [jobId]);

  useEffect(() => {
    void refreshJob();
  }, [refreshJob]);

  useEffect(() => {
    void refreshLogs();
  }, [refreshLogs, job?.status]);

  useEffect(() => {
    if (!jobId || !job || !active.has(job.status)) return;
    const t = window.setInterval(() => {
      void refreshJob();
      void refreshLogs();
    }, 1000);
    return () => window.clearInterval(t);
  }, [jobId, job?.status, refreshJob, refreshLogs]);

  if (!jobId) return <p className="error">Missing job id</p>;

  const back = job ? backLinkForKind(String(job.kind)) : backLinkForKind("");

  return (
    <section aria-label="Job detail" className="game-surface detail-shell detail-arcade">
      <header className="surface-hero">
        <p className="surface-hero__topline">Job detail</p>
        <h1 className="page-title">Job {jobId}</h1>
        <p className="detail-nav">
          <Link to={back.to}>{back.label}</Link>
          {" · "}
          <Link to="/">Cockpit</Link>
        </p>
      </header>
      {err && <p className="error">{err}</p>}
      <section className="panel surface-panel">
        <p className="surface-kicker">Queue card</p>
        <h2>Status</h2>
        {job == null && !err && <p className="muted">Loading…</p>}
        {job != null && (
          <>
            <p>
              <strong>{job.kind}</strong> · {job.status}
            </p>
            {job.error && <p className="error">{job.error}</p>}
            {job.kind === "evaluation" &&
              (job.status === "succeeded" || job.status === "failed") && (
                <p>
                  <Link to={`/evaluations/${job.job_id}`}>
                    Open evaluation record
                  </Link>
                </p>
              )}
            <h3 style={{ fontSize: "0.95rem", marginTop: "1rem" }}>Config</h3>
            <pre className="inspector-raw inspector-raw--tight">
              {JSON.stringify(job.config, null, 2)}
            </pre>
            {job.kind === "training" &&
              job.status === "succeeded" &&
              (() => {
                const training = readTrainingMetrics(job.result);
                if (!training) return null;
                const endedBy = training["ended_by"];
                const perGame = training["per_game"];
                return (
                  <>
                    <h3 style={{ fontSize: "0.95rem", marginTop: "1rem" }}>
                      Training metrics
                    </h3>
                    <dl
                      className="training-summary"
                      style={{
                        display: "grid",
                        gridTemplateColumns: "auto 1fr",
                        gap: "0.25rem 1rem",
                        marginTop: "0.5rem",
                        fontSize: "0.9rem",
                      }}
                    >
                      {TRAINING_SUMMARY_KEYS.map(([key, label]) => {
                        if (!(key in training)) return null;
                        const v = training[key];
                        if (v === undefined || v === null) return null;
                        return (
                          <Fragment key={key}>
                            <dt style={{ fontWeight: 600 }}>{label}</dt>
                            <dd style={{ margin: 0 }}>
                              {formatMetricValue(v)}
                            </dd>
                          </Fragment>
                        );
                      })}
                      {endedBy != null &&
                        typeof endedBy === "object" &&
                        !Array.isArray(endedBy) && (
                          <>
                            <dt style={{ fontWeight: 600 }}>Games by outcome</dt>
                            <dd style={{ margin: 0 }}>
                              {formatMetricValue(endedBy)}
                            </dd>
                          </>
                        )}
                      {Array.isArray(perGame) && (
                        <>
                          <dt style={{ fontWeight: 600 }}>Per-game rows</dt>
                          <dd style={{ margin: 0 }}>{perGame.length} games</dd>
                        </>
                      )}
                    </dl>
                  </>
                );
              })()}
            <h3 style={{ fontSize: "0.95rem", marginTop: "1rem" }}>Result</h3>
            <pre className="inspector-raw">
              {JSON.stringify(job.result, null, 2)}
            </pre>
          </>
        )}
      </section>

      <section className="panel surface-panel">
        <p className="surface-kicker">Terminal feed</p>
        <h2>Log stream</h2>
        {logs == null && <p className="muted">No log slice yet.</p>}
        {logs != null && (
          <pre className="log-viewer">
            {logs.lines.length === 0
              ? "(empty)"
              : logs.lines.join("\n")}
          </pre>
        )}
      </section>
    </section>
  );
}
