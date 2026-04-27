import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  getJob,
  listEvaluations,
  listJobs,
  listStrategies,
  startEval,
} from "../api/client";
import type { EvaluationListItem, JobDetail, StrategiesResponse } from "../api/types";

const DEFAULT_BASELINES = [
  "basic",
  "aggressive",
  "defensive",
  "set_completion",
];

export function EvaluationLabPage() {
  const [searchParams, setSearchParams] = useSearchParams();
  const [strategies, setStrategies] = useState<StrategiesResponse | null>(null);
  const [cand, setCand] = useState("basic");
  const [candCustom, setCandCustom] = useState("");
  const [useCustomCand, setUseCustomCand] = useState(false);
  const [pc, setPc] = useState(2);
  const [games, setGames] = useState(2);
  const [seed, setSeed] = useState(1);
  const [maxTurns, setMaxTurns] = useState(200);
  const [maxSelfPlay, setMaxSelfPlay] = useState(30_000);
  const [baselinePick, setBaselinePick] = useState<Record<string, boolean>>({});
  const [championsPath, setChampionsPath] = useState("");
  const [promoteIfPasses, setPromoteIfPasses] = useState(false);
  const [maxAbortedRate, setMaxAbortedRate] = useState(0);

  const [jobId, setJobId] = useState<string | null>(null);
  const [status, setStatus] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [evalJobs, setEvalJobs] = useState<JobDetail[]>([]);
  const [evalRows, setEvalRows] = useState<EvaluationListItem[]>([]);

  const builtIns = strategies?.built_in ?? DEFAULT_BASELINES;

  useEffect(() => {
    const initial: Record<string, boolean> = {};
    for (const b of DEFAULT_BASELINES) initial[b] = true;
    setBaselinePick(initial);
  }, []);

  useEffect(() => {
    const fromQuery = searchParams.get("candidate");
    const promote = searchParams.get("promote");
    const ch = searchParams.get("champions");
    if (fromQuery) {
      setCandCustom(fromQuery);
      setUseCustomCand(true);
      setCand(fromQuery);
    }
    if (promote === "1" || promote === "true") setPromoteIfPasses(true);
    if (ch) setChampionsPath(ch);
  }, [searchParams]);

  const loadLists = useCallback(() => {
    void Promise.all([
      listJobs({ kind: "evaluation", limit: 15 }),
      listEvaluations({ limit: 10 }),
    ])
      .then(([j, e]) => {
        setEvalJobs(j.items);
        setEvalRows(e.items);
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
    loadLists();
    return () => {
      c = true;
    };
  }, [loadLists]);

  useEffect(() => {
    if (!jobId) return;
    let n = 0;
    const t = window.setInterval(async () => {
      n += 1;
      if (n > 600) {
        window.clearInterval(t);
        return;
      }
      try {
        const j = await getJob(jobId);
        setStatus(String(j.status));
        if (j.status === "succeeded" || j.status === "failed") {
          window.clearInterval(t);
        }
        loadLists();
      } catch {
        /* ignore */
      }
    }, 500);
    return () => window.clearInterval(t);
  }, [jobId, loadLists]);

  const selectedBaselines = useMemo(
    () => builtIns.filter((b) => baselinePick[b]),
    [baselinePick, builtIns]
  );

  const effectiveCandidate = useCustomCand ? candCustom.trim() : cand;

  async function go() {
    setErr(null);
    if (!effectiveCandidate) {
      setErr("Choose or enter a candidate strategy.");
      return;
    }
    const baselines =
      selectedBaselines.length > 0 ? selectedBaselines : ["basic"];
    try {
      const r = await startEval({
        candidate: effectiveCandidate,
        player_count: pc,
        baselines,
        games,
        seed,
        max_turns: maxTurns,
        max_self_play_steps: maxSelfPlay,
        champions_manifest_path: championsPath.trim() || null,
        promote_if_passes: promoteIfPasses,
        max_aborted_rate: maxAbortedRate,
      });
      setJobId(r.job_id);
      setStatus(r.status);
      loadLists();
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  function clearPromotionQuery() {
    const next = new URLSearchParams(searchParams);
    next.delete("candidate");
    next.delete("promote");
    next.delete("champions");
    setSearchParams(next, { replace: true });
  }

  return (
    <section aria-label="Evaluation console" className="game-surface page-console lab-console">
      <header className="surface-hero">
        <p className="surface-hero__topline">Evaluation console</p>
        <h1 className="page-title">Evaluation Lab</h1>
        <p className="surface-hero__copy">
          Candidate vs baselines; optional champion manifest and automatic
          promotion for neural checkpoints that pass guardrails.
        </p>
      </header>
      {searchParams.get("candidate") && (
        <p className="muted">
          Form prefilled from checkpoint promotion shortcut.{" "}
          <button type="button" onClick={() => clearPromotionQuery()}>
            Clear query params
          </button>
        </p>
      )}
      {err && <p className="error">{err}</p>}

      <section className="panel surface-panel">
        <p className="surface-kicker">Score gauntlet</p>
        <h2>New evaluation</h2>
        <div className="form-stack">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={useCustomCand}
              onChange={(e) => setUseCustomCand(e.target.checked)}
            />
            Custom candidate (e.g. neural:…)
          </label>
          {useCustomCand ? (
            <label>
              Candidate{" "}
              <input
                style={{ width: "100%", maxWidth: "28rem" }}
                value={candCustom}
                onChange={(e) => setCandCustom(e.target.value)}
                placeholder="neural:checkpoints/foo/run-001.pt"
              />
            </label>
          ) : (
            <label>
              Candidate{" "}
              <select
                value={cand}
                onChange={(e) => setCand(e.target.value)}
              >
                {builtIns.map((b) => (
                  <option key={b} value={b}>
                    {b}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            Players{" "}
            <select
              value={pc}
              onChange={(e) => setPc(parseInt(e.target.value, 10))}
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
              value={games}
              onChange={(e) => setGames(parseInt(e.target.value, 10) || 1)}
            />
          </label>
          <label>
            Seed{" "}
            <input
              type="number"
              value={seed}
              onChange={(e) => setSeed(parseInt(e.target.value, 10) || 0)}
            />
          </label>
          <label>
            Max turns{" "}
            <input
              type="number"
              min={1}
              value={maxTurns}
              onChange={(e) =>
                setMaxTurns(parseInt(e.target.value, 10) || 1)
              }
            />
          </label>
          <label>
            Max self-play steps{" "}
            <input
              type="number"
              min={1000}
              value={maxSelfPlay}
              onChange={(e) =>
                setMaxSelfPlay(parseInt(e.target.value, 10) || 1000)
              }
            />
          </label>
        </div>

        <h3 style={{ fontSize: "0.95rem", marginTop: "1rem" }}>Baselines</h3>
        <div className="row" style={{ marginBottom: "0.5rem" }}>
          {builtIns.map((b) => (
            <label key={b}>
              <input
                type="checkbox"
                checked={baselinePick[b] ?? false}
                onChange={(e) =>
                  setBaselinePick((p) => ({ ...p, [b]: e.target.checked }))
                }
              />{" "}
              {b}
            </label>
          ))}
        </div>

        <h3 style={{ fontSize: "0.95rem", marginTop: "1rem" }}>
          Promotion (neural only)
        </h3>
        <div className="form-stack">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={promoteIfPasses}
              onChange={(e) => setPromoteIfPasses(e.target.checked)}
            />
            Promote if passes guardrails
          </label>
          <label>
            Champions manifest path (relative to artifact root or absolute){" "}
            <input
              style={{ width: "100%", maxWidth: "28rem" }}
              value={championsPath}
              onChange={(e) => setChampionsPath(e.target.value)}
              placeholder="champions.json"
            />
          </label>
          <label>
            Max aborted rate [0–1]{" "}
            <input
              type="number"
              min={0}
              max={1}
              step={0.01}
              value={maxAbortedRate}
              onChange={(e) =>
                setMaxAbortedRate(parseFloat(e.target.value) || 0)
              }
            />
          </label>
        </div>

        <button
          className="pixel-button"
          type="button"
          style={{ marginTop: "0.75rem" }}
          onClick={() => void go()}
        >
          Start evaluation job
        </button>
      </section>

      {jobId && (
        <p style={{ marginTop: "0.75rem" }}>
          Job <Link to={`/jobs/${jobId}`}><code>{jobId}</code></Link> —{" "}
          <strong>{status}</strong>
          {status === "succeeded" && (
            <>
              {" "}
              ·{" "}
              <Link to={`/evaluations/${jobId}`}>evaluation record</Link>
            </>
          )}
        </p>
      )}

      <div className="layout-two">
        <section className="panel surface-panel">
          <p className="surface-kicker">Queue monitor</p>
          <h2>Evaluation jobs</h2>
          {evalJobs.length === 0 && <p className="muted">None yet.</p>}
          {evalJobs.map((j) => (
            <div className="job-item" key={j.job_id}>
              <Link to={`/jobs/${j.job_id}`}>{j.job_id}</Link>{" "}
              <span className="muted">
                {j.status}
                {j.status === "succeeded" && (
                  <>
                    {" "}
                    ·{" "}
                    <Link to={`/evaluations/${j.job_id}`}>detail</Link>
                  </>
                )}
              </span>
              {(() => {
                const promo = j.result?.promotion;
                if (
                  promo == null ||
                  typeof promo !== "object" ||
                  !("promoted" in promo)
                ) {
                  return null;
                }
                return (
                  <p className="muted" style={{ margin: "0.25rem 0 0" }}>
                    Promotion: {String(promo.promoted)}
                  </p>
                );
              })()}
            </div>
          ))}
        </section>
        <section className="panel surface-panel">
          <p className="surface-kicker">Score archive</p>
          <h2>Recorded evaluations</h2>
          {evalRows.length === 0 && <p className="muted">None persisted.</p>}
          {evalRows.map((ev) => (
            <div className="job-item" key={ev.id}>
              <Link to={`/evaluations/${ev.id}`}>{ev.id}</Link>{" "}
              <span className="muted">
                score {ev.candidate_score.toFixed(3)} · {ev.candidate}
                {ev.promoted === true ? (
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
