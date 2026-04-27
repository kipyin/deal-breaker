import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import {
  getGameInspector,
  postAction,
  postAiStep,
  replayLink,
  type Inspector,
} from "../api/client";
import type { InspectorState, JsonObject } from "../api/types";
import {
  EventTimeline,
  RawInspectorJson,
} from "../features/inspector";
import { PlayTable } from "../features/play";

export function PlayInspectorPage() {
  const { gameId } = useParams<{ gameId: string }>();
  const [ins, setIns] = useState<Inspector | null>(null);
  const [version, setVersion] = useState(0);
  const [err, setErr] = useState<string | null>(null);
  const [replayId, setReplayId] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    if (!gameId) return;
    const v = await getGameInspector(gameId, "P1");
    setIns(v);
    setVersion(v.version ?? 0);
  }, [gameId]);

  useEffect(() => {
    void refresh().catch((e) => setErr(e instanceof Error ? e.message : String(e)));
  }, [refresh]);

  async function applyAction(payload: JsonObject) {
    if (!gameId) return;
    setErr(null);
    try {
      const r = await postAction(gameId, {
        player_id: "P1",
        expected_version: version,
        action: payload,
      });
      setIns(r.inspector);
      setVersion(r.version);
      if (r.inspector.status === "completed") {
        const link = await replayLink(gameId);
        setReplayId(link.replay_id);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  async function runAi() {
    if (!gameId) return;
    setErr(null);
    try {
      const r = await postAiStep(gameId, { expected_version: version, max_steps: 30 });
      setIns(r.inspector);
      setVersion(r.version);
      if (r.done === "terminal") {
        const link = await replayLink(gameId);
        setReplayId(link.replay_id);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }

  if (!gameId) return <p className="error">Missing game id</p>;

  const st = ins as InspectorState | null;
  const status = String(st?.status ?? "");

  return (
    <section aria-label="Live play console" className="game-surface page-console play-page play-page--session">
      <PlayTable
        state={st}
        onChoose={(payload) => void applyAction(payload)}
        onRunAi={() => void runAi()}
        readOnly={status === "completed"}
        flashMessage={err}
      />

      <header className="surface-hero surface-hero--after-table surface-hero--session">
        <p className="surface-hero__topline">Session</p>
        <h1 className="page-title page-title--session">Play · {gameId}</h1>
        <p className="surface-hero__copy">
          Card-first play on the felt. Expand developer details for version, the event timeline, and
          raw inspector JSON.
        </p>
        {replayId && (
          <p className="surface-hero__copy">
            Game finished.{" "}
            <Link to={`/replays/${replayId}`}>Open replay inspector</Link>
          </p>
        )}
      </header>

      {err != null && ins == null ? <p className="error">{err}</p> : null}

      <details className="dev-details pixel-panel play-page__dev">
        <summary>Developer details</summary>
        <div className="dev-details__body">
          <p className="muted">
            Inspector version <strong>{version}</strong>
            {st?.phase != null ? (
              <>
                {" "}
                · phase <strong>{st.phase}</strong>
              </>
            ) : null}
          </p>
          <p>
            <button
              type="button"
              className="pixel-button pixel-button--secondary"
              onClick={() => void refresh()}
            >
              Refresh inspector
            </button>
          </p>
          <EventTimeline events={st?.timeline} />
          <RawInspectorJson data={ins as JsonObject | null} defaultOpen={false} />
        </div>
      </details>
    </section>
  );
}
