import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { getReplayInspector, type Inspector } from "../api/client";
import type { InspectorState, JsonObject, ReplayInspectorMeta } from "../api/types";
import {
  BoardState,
  EventTimeline,
  GameStatusBar,
  LastActionSummary,
  LegalActionPanel,
  PendingState,
  RawInspectorJson,
  ReplayStepControls,
} from "../features/inspector";
import { PlayTable } from "../features/play";

export function ReplayInspectorPage() {
  const { replayId } = useParams<{ replayId: string }>();
  const [step, setStep] = useState(0);
  const [data, setData] = useState<Inspector | null>(null);
  const [meta, setMeta] = useState<ReplayInspectorMeta | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!replayId) return;
    setErr(null);
    try {
      const v = await getReplayInspector(replayId, step, "P1");
      setData(v);
      if (v.replay) setMeta(v.replay);
    } catch (e) {
      setErr(e instanceof Error ? e.message : String(e));
    }
  }, [replayId, step]);

  useEffect(() => {
    void load();
  }, [load]);

  if (!replayId) return <p className="error">Missing replay id</p>;

  const st = data as InspectorState | null;
  const maxStep = meta?.max_step ?? 0;
  const noop = () => undefined;

  return (
    <section aria-label="Replay console" className="game-surface page-console replay-console">
      {err && <p className="error">{err}</p>}
      {meta && (
        <ReplayStepControls
          step={step}
          maxStep={maxStep}
          disabled={!meta}
          onStepChange={setStep}
        />
      )}
      {meta == null && <p className="muted">Loading replay bounds…</p>}
      <GameStatusBar
        state={st}
        extra={
          meta ? (
            <span className="muted">
              Action step {meta.step} of {maxStep} (version {st?.version ?? 0})
            </span>
          ) : null
        }
      />

      <PlayTable state={st} onChoose={noop} onRunAi={noop} readOnly flashMessage={null} />

      <header className="surface-hero surface-hero--after-table">
        <p className="surface-hero__topline">Replay</p>
        <h1 className="page-title">Replay · {replayId}</h1>
        <p className="surface-hero__copy">
          Same felt as live play, read-only. Open the step inspector for legal actions, board, and
          raw JSON.
        </p>
        <div className="surface-toolbar">
          <Link className="pixel-button pixel-button--secondary" to="/play">
            Start another game
          </Link>
        </div>
      </header>

      <details className="dev-details pixel-panel">
        <summary>Step inspector (panels)</summary>
        <div className="dev-details__body">
          <div className="layout-two">
            <div className="dev-details__stack">
              <LegalActionPanel
                title="Actions available at this step"
                legalActions={st?.legal_actions}
                readOnly
                emptyMessage="No legal actions (terminal state or loading)."
              />
              <PendingState pending={st?.pending} />
              <LastActionSummary state={st} />
            </div>
            <BoardState state={st} />
          </div>
          <EventTimeline
            events={st?.timeline}
            stepLabel={
              meta
                ? `State after ${meta.step} action log entr${maxStep === 1 ? "y" : "ies"}. ${maxStep} total.`
                : undefined
            }
          />
          <RawInspectorJson data={data as JsonObject | null} defaultOpen={false} />
        </div>
      </details>
    </section>
  );
}
