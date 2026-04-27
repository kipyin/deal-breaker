import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  listCheckpoints,
  listJobs,
  listStrategies,
  startArtifactImport,
  startRlSearch,
  startTraining,
} from "../api/client";
import type { CheckpointListItem, JobDetail, StrategiesResponse } from "../api/types";

const DEFAULT_BASELINES = [
  "basic",
  "aggressive",
  "defensive",
  "set_completion",
];

export function TrainingLabPage() {
  const [strategies, setStrategies] = useState<StrategiesResponse | null>(null);
  const [jobs, setJobs] = useState<JobDetail[]>([]);
  const [checkpoints, setCheckpoints] = useState<CheckpointListItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [lastJob, setLastJob] = useState<string | null>(null);

  const [trainPc, setTrainPc] = useState(2);
  const [trainGames, setTrainGames] = useState(10);
  const [trainSeed, setTrainSeed] = useState(1);
  const [trainLabel, setTrainLabel] = useState("");
  const [championId, setChampionId] = useState("");

  const [rlPc2, setRlPc2] = useState(true);
  const [rlPc3, setRlPc3] = useState(true);
  const [rlPc4, setRlPc4] = useState(true);
  const [rlPc5, setRlPc5] = useState(true);
  const [rlRuns, setRlRuns] = useState(1);
  const [rlGames, setRlGames] = useState(10);
  const [rlSeed, setRlSeed] = useState(1);

  const [importPath, setImportPath] = useState("checkpoints/rl-search");

  const refresh = useCallback(() => {
    void Promise.all([
      listJobs({ limit: 12 }),
      listCheckpoints({ limit: 12 }),
    ])
      .then(([j, c]) => {
        setJobs(j.items);
        setCheckpoints(c.items);
      })
      .catch(() => null);
  }, []);

  useEffect(() => {
    let c = false;
    (async () => {
      try {
        const s = await listStrategies();
        if (!c) setStrategies(s);
      } catch (e) {
        if (!c) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    refresh();
    return () => {
      c = true;
    };
  }, [refresh]);

  const opponentPool = strategies?.built_in ?? DEFAULT_BASELINES;

  async function submitTraining() {
    setErr(null);
    setBusy("training");
    try {
      const r = await startTraining({
        player_count: trainPc,
        games: trainGames,
        seed: trainSeed,
        opponent_strategies: [...opponentPool],
        checkpoint_label: trainLabel.trim() || null,
        champion_checkpoint_id: championId.trim() || null,
      });
      setLastJob(r.job_id);
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function submitRlSearch() {
    const player_counts: number[] = [];
    if (rlPc2) player_counts.push(2);
    if (rlPc3) player_counts.push(3);
    if (rlPc4) player_counts.push(4);
    if (rlPc5) player_counts.push(5);
    if (player_counts.length === 0) {
      setErr("Select at least one player count for RL search.");
      return;
    }
    setErr(null);
    setBusy("rl_search");
    try {
      const r = await startRlSearch({
        player_counts,
        runs_per_count: rlRuns,
        games_per_run: rlGames,
        seed: rlSeed,
        opponent_strategies: [...opponentPool],
        champion_checkpoint_id: championId.trim() || null,
      });
      setLastJob(r.job_id);
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  async function submitImport() {
    setErr(null);
    setBusy("import");
    try {
      const r = await startArtifactImport({ rel_path: importPath.trim() });
      setLastJob(r.job_id);
      refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(null);
    }
  }

  const labJobs = jobs.filter((j) =>
    ["training", "rl_search", "artifact_import"].includes(j.kind)
  );

  return (
    <section aria-label="Training console" className="game-surface page-console lab-console">
      <header className="surface-hero">
        <p className="surface-hero__topline">Training console</p>
        <h1 className="page-title">Training Lab</h1>
        <p className="surface-hero__copy">
          Self-play training, RL search sweeps, and artifact imports enqueue
          local jobs. Follow progress under <Link to="/">Cockpit</Link> or open
          a job for logs.
        </p>
      </header>
      {strategies && (
        <p className="muted">
          <small>{strategies.hint}</small>
        </p>
      )}
      {err && <p className="error">{err}</p>}
      {lastJob && (
        <p>
          Last enqueue:{" "}
          <Link to={`/jobs/${lastJob}`}>
            <code>{lastJob}</code>
          </Link>
        </p>
      )}

      <div className="layout-two">
        <section className="panel surface-panel">
          <p className="surface-kicker">Self-play deck</p>
          <h2>Self-play training</h2>
          <div className="form-stack">
            <label>
              Players{" "}
              <select
                value={trainPc}
                onChange={(e) => setTrainPc(parseInt(e.target.value, 10))}
              >
                <option value={2}>2</option>
                <option value={3}>3</option>
                <option value={4}>4</option>
                <option value={5}>5</option>
              </select>
            </label>
            <label>
              Games{" "}
              <input
                type="number"
                min={1}
                value={trainGames}
                onChange={(e) =>
                  setTrainGames(parseInt(e.target.value, 10) || 1)
                }
              />
            </label>
            <label>
              Seed{" "}
              <input
                type="number"
                value={trainSeed}
                onChange={(e) =>
                  setTrainSeed(parseInt(e.target.value, 10) || 0)
                }
              />
            </label>
            <label>
              Checkpoint label (optional){" "}
              <input
                value={trainLabel}
                onChange={(e) => setTrainLabel(e.target.value)}
                placeholder="run label"
              />
            </label>
            <label>
              Champion checkpoint id (optional){" "}
              <input
                value={championId}
                onChange={(e) => setChampionId(e.target.value)}
                placeholder="ckpt_…"
              />
            </label>
          </div>
          <button
            className="pixel-button"
            type="button"
            style={{ marginTop: "0.75rem" }}
            disabled={busy !== null}
            onClick={() => void submitTraining()}
          >
            {busy === "training" ? "Starting…" : "Start training job"}
          </button>
        </section>

        <section className="panel surface-panel">
          <p className="surface-kicker">Search sweep</p>
          <h2>RL search</h2>
          <p className="muted" style={{ marginTop: 0 }}>
            Player counts (multi-select)
          </p>
          <div className="row" style={{ marginBottom: "0.5rem" }}>
            <label>
              <input
                type="checkbox"
                checked={rlPc2}
                onChange={(e) => setRlPc2(e.target.checked)}
              />{" "}
              2p
            </label>
            <label>
              <input
                type="checkbox"
                checked={rlPc3}
                onChange={(e) => setRlPc3(e.target.checked)}
              />{" "}
              3p
            </label>
            <label>
              <input
                type="checkbox"
                checked={rlPc4}
                onChange={(e) => setRlPc4(e.target.checked)}
              />{" "}
              4p
            </label>
            <label>
              <input
                type="checkbox"
                checked={rlPc5}
                onChange={(e) => setRlPc5(e.target.checked)}
              />{" "}
              5p
            </label>
          </div>
          <div className="form-stack">
            <label>
              Runs per count{" "}
              <input
                type="number"
                min={1}
                value={rlRuns}
                onChange={(e) => setRlRuns(parseInt(e.target.value, 10) || 1)}
              />
            </label>
            <label>
              Games per run{" "}
              <input
                type="number"
                min={1}
                value={rlGames}
                onChange={(e) => setRlGames(parseInt(e.target.value, 10) || 1)}
              />
            </label>
            <label>
              Seed{" "}
              <input
                type="number"
                value={rlSeed}
                onChange={(e) =>
                  setRlSeed(parseInt(e.target.value, 10) || 0)
                }
              />
            </label>
          </div>
          <button
            className="pixel-button"
            type="button"
            style={{ marginTop: "0.75rem" }}
            disabled={busy !== null}
            onClick={() => void submitRlSearch()}
          >
            {busy === "rl_search" ? "Starting…" : "Start RL search job"}
          </button>
        </section>
      </div>

      <section className="panel surface-panel">
        <p className="surface-kicker">Artifact intake</p>
        <h2>Import RL search tree</h2>
        <p className="muted" style={{ marginTop: 0 }}>
          Relative path under the artifact root (e.g.{" "}
          <code>checkpoints/rl-search</code>).
        </p>
        <div className="row">
          <input
            style={{ flex: "1 1 12rem", minWidth: "8rem" }}
            value={importPath}
            onChange={(e) => setImportPath(e.target.value)}
          />
          <button
            className="pixel-button pixel-button--secondary"
            type="button"
            disabled={busy !== null}
            onClick={() => void submitImport()}
          >
            {busy === "import" ? "Starting…" : "Enqueue import"}
          </button>
        </div>
      </section>

      <div className="layout-two">
        <section className="panel surface-panel">
          <p className="surface-kicker">Queue monitor</p>
          <h2>Recent training / search / import jobs</h2>
          {labJobs.length === 0 && (
            <p className="muted">No jobs yet for these kinds.</p>
          )}
          {labJobs.map((job) => (
            <div className="job-item" key={job.job_id}>
              <Link to={`/jobs/${job.job_id}`}>{job.job_id}</Link>{" "}
              <span className="muted">
                {job.kind} · {job.status}
              </span>
            </div>
          ))}
        </section>
        <section className="panel surface-panel">
          <p className="surface-kicker">Checkpoint stack</p>
          <h2>Latest checkpoints</h2>
          {checkpoints.length === 0 && (
            <p className="muted">No checkpoints indexed.</p>
          )}
          {checkpoints.map((checkpoint) => (
            <div className="job-item" key={checkpoint.id}>
              <Link to={`/checkpoints/${checkpoint.id}`}>
                {checkpoint.label ?? checkpoint.id}
              </Link>{" "}
              <span className="muted">
                P{checkpoint.player_count ?? "?"} · {checkpoint.strategy_spec}
                {checkpoint.promoted ? (
                  <>
                    {" "}
                    <span className="tag tag--promoted">promoted</span>
                  </>
                ) : null}
              </span>
            </div>
          ))}
        </section>
      </div>
    </section>
  );
}
