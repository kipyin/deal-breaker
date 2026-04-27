import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import {
  getHealth,
  listCheckpoints,
  listEvaluations,
  listGames,
  listJobs,
  listReplays,
  listChampions,
} from "../api/client";
import type {
  CheckpointListItem,
  EvaluationListItem,
  GameListItem,
  JobDetail,
  ReplayListItem,
} from "../api/types";

export function CockpitPage() {
  const [ok, setOk] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [jobs, setJobs] = useState<JobDetail[] | null>(null);
  const [champions, setChampions] = useState<CheckpointListItem[] | null>(null);
  const [checkpoints, setCheckpoints] = useState<CheckpointListItem[] | null>(null);
  const [games, setGames] = useState<GameListItem[] | null>(null);
  const [replays, setReplays] = useState<ReplayListItem[] | null>(null);
  const [evaluations, setEvaluations] = useState<EvaluationListItem[] | null>(
    null
  );

  useEffect(() => {
    let c = true;
    (async () => {
      try {
        const h = await getHealth();
        if (!c) return;
        setOk(h.status);
        const [
          jobRows,
          championRows,
          ckptRows,
          gameRows,
          replayRows,
          evalRows,
        ] = await Promise.all([
          listJobs({ limit: 8 }),
          listChampions(),
          listCheckpoints({ limit: 6 }),
          listGames({ limit: 6 }),
          listReplays({ limit: 6 }),
          listEvaluations({ limit: 6 }),
        ]);
        if (!c) return;
        setJobs(jobRows.items);
        setChampions(championRows.items);
        setCheckpoints(ckptRows.items);
        setGames(gameRows.items);
        setReplays(replayRows.items);
        setEvaluations(evalRows.items);
      } catch (e) {
        if (c) setErr(e instanceof Error ? e.message : String(e));
      }
    })();
    return () => {
      c = false;
    };
  }, []);

  return (
    <section aria-label="Command deck" className="game-surface page-console cockpit-console">
      <header className="surface-hero">
        <p className="surface-hero__topline">Pixel property command center</p>
        <h1 className="page-title">Cockpit</h1>
        {err && <p className="error">Backend: {err}</p>}
        {!err && (
          <p className="surface-hero__copy">
            API <strong>{ok ?? "…"}</strong> · local lab overview, champions,
            and recent activity.
          </p>
        )}
        <div className="surface-hero__meta">
          <span className="status-chip status-chip--accent">Live Lab</span>
          <span className="status-chip">Neon Deck</span>
        </div>
      </header>

      <div className="cockpit-quick pixel-panel surface-panel">
        <p className="surface-kicker">Quick actions</p>
        <div className="surface-toolbar">
          <Link className="pixel-button" to="/play">
            Open table setup
          </Link>
          <Link className="pixel-button pixel-button--secondary" to="/train">
            Training lab
          </Link>
          <Link className="pixel-button pixel-button--secondary" to="/evaluate">
            Run evaluation
          </Link>
          <Link className="pixel-button pixel-button--secondary" to="/artifacts">
            Browse artifacts
          </Link>
        </div>
      </div>

      <div className="cockpit-grid">
        <section className="panel surface-panel command-card">
          <p className="surface-kicker">Promoted Stack</p>
          <h2>Champion Board</h2>
          {champions == null && <p className="muted">Loading…</p>}
          {champions != null && champions.length === 0 && (
            <p className="muted">No promoted checkpoints yet.</p>
          )}
          {champions != null &&
            champions.map((cp) => (
              <div key={cp.id} className="job-item">
                <Link to={`/checkpoints/${cp.id}`}>
                  {cp.label ?? cp.id}
                </Link>
                <span className="muted">
                  {" "}
                  P{cp.player_count ?? "?"} · {cp.strategy_spec}
                </span>
              </div>
            ))}
        </section>

        <section className="panel surface-panel command-card">
          <p className="surface-kicker">Checkpoint Stack</p>
          <h2>Latest checkpoints</h2>
          {checkpoints == null && <p className="muted">Loading…</p>}
          {checkpoints != null && checkpoints.length === 0 && (
            <p className="muted">None indexed — train or import artifacts.</p>
          )}
          {checkpoints != null &&
            checkpoints.map((cp) => (
              <div key={cp.id} className="job-item">
                <Link to={`/checkpoints/${cp.id}`}>
                  {cp.label ?? cp.id}
                </Link>
                <span className="muted">
                  {" "}
                  {cp.promoted ? (
                    <span className="tag tag--promoted">promoted</span>
                  ) : null}{" "}
                  P{cp.player_count ?? "?"}
                </span>
              </div>
            ))}
        </section>

        <section className="panel surface-panel command-card">
          <p className="surface-kicker">Job Queue</p>
          <h2>Recent jobs</h2>
          {jobs == null && <p className="muted">Loading…</p>}
          {jobs != null && jobs.length === 0 && (
            <p className="muted">No jobs yet.</p>
          )}
          {jobs != null &&
            jobs.map((j) => (
              <div key={j.job_id} className="job-item">
                <Link to={`/jobs/${j.job_id}`}>{j.job_id}</Link>{" "}
                <span className="muted">
                  {j.kind} · {j.status}
                </span>
              </div>
            ))}
        </section>

        <section className="panel surface-panel command-card">
          <p className="surface-kicker">Table History</p>
          <h2>Recent games</h2>
          {games == null && <p className="muted">Loading…</p>}
          {games != null && games.length === 0 && (
            <p className="muted">No recorded games.</p>
          )}
          {games != null &&
            games.map((g) => (
              <div key={g.game_id} className="job-item">
                <Link to={`/play/${g.game_id}`}>{g.game_id}</Link>{" "}
                <span className="muted">
                  {g.status} · {g.turn_count} turns
                </span>
              </div>
            ))}
        </section>

        <section className="panel surface-panel command-card">
          <p className="surface-kicker">Replay Shelf</p>
          <h2>Recent replays</h2>
          {replays == null && <p className="muted">Loading…</p>}
          {replays != null && replays.length === 0 && (
            <p className="muted">No replays indexed.</p>
          )}
          {replays != null &&
            replays.map((r) => (
              <div key={r.replay_id} className="job-item">
                <Link to={`/replays/${r.replay_id}`}>{r.replay_id}</Link>{" "}
                <span className="muted">{r.event_count} events</span>
              </div>
            ))}
        </section>

        <section className="panel surface-panel command-card">
          <p className="surface-kicker">Score Reports</p>
          <h2>Latest evaluations</h2>
          {evaluations == null && <p className="muted">Loading…</p>}
          {evaluations != null && evaluations.length === 0 && (
            <p className="muted">No evaluations yet.</p>
          )}
          {evaluations != null &&
            evaluations.map((ev) => (
              <div key={ev.id} className="job-item">
                <Link to={`/evaluations/${ev.id}`}>{ev.id}</Link>{" "}
                <span className="muted">
                  score {ev.candidate_score.toFixed(3)} ·{" "}
                  {ev.promoted === true ? (
                    <span className="tag tag--promoted">promoted</span>
                  ) : ev.promoted === false ? (
                    "not promoted"
                  ) : (
                    "—"
                  )}
                </span>
              </div>
            ))}
        </section>
      </div>
    </section>
  );
}
