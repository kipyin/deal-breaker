import type { ReactElement } from "react";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";
import {
  getArtifact,
  getCheckpoint,
  getEvaluation,
  getGameInspector,
  getJob,
  getJobLogs,
  getReplayInspector,
  listArtifacts,
  listChampions,
  listCheckpoints,
  listEvaluations,
  listGames,
  listJobs,
  listReplays,
  listStrategies,
} from "../api/client";
import { ArtifactBrowserPage } from "./ArtifactBrowserPage";
import { ArtifactDetailPage } from "./ArtifactDetailPage";
import { CheckpointDetailPage } from "./CheckpointDetailPage";
import { CockpitPage } from "./CockpitPage";
import { EvaluationDetailPage } from "./EvaluationDetailPage";
import { EvaluationLabPage } from "./EvaluationLabPage";
import { JobDetailPage } from "./JobDetailPage";
import { NewGamePage } from "./NewGamePage";
import { PlayInspectorPage } from "./PlayInspectorPage";
import { ReplayInspectorPage } from "./ReplayInspectorPage";
import { TrainingLabPage } from "./TrainingLabPage";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    getArtifact: vi.fn(),
    getCheckpoint: vi.fn(),
    getEvaluation: vi.fn(),
    getGameInspector: vi.fn(),
    getHealth: vi.fn().mockResolvedValue({ status: "ok" }),
    getJob: vi.fn(),
    getJobLogs: vi.fn(),
    getReplayInspector: vi.fn(),
    listArtifacts: vi.fn(),
    listChampions: vi.fn(),
    listCheckpoints: vi.fn(),
    listEvaluations: vi.fn(),
    listGames: vi.fn(),
    listJobs: vi.fn(),
    listReplays: vi.fn(),
    listStrategies: vi.fn(),
    newGame: vi.fn(),
    postAction: vi.fn(),
    postAiStep: vi.fn(),
    replayLink: vi.fn(),
  };
});

const emptyList = { items: [] };

function renderAt(path: string, element: ReactElement, routePath = path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path={routePath} element={element} />
      </Routes>
    </MemoryRouter>
  );
}

describe("restyled app page surfaces", () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  test("renders cockpit as a command deck", async () => {
    vi.mocked(listJobs).mockResolvedValue(emptyList);
    vi.mocked(listChampions).mockResolvedValue(emptyList);
    vi.mocked(listCheckpoints).mockResolvedValue(emptyList);
    vi.mocked(listGames).mockResolvedValue(emptyList);
    vi.mocked(listReplays).mockResolvedValue(emptyList);
    vi.mocked(listEvaluations).mockResolvedValue(emptyList);

    renderAt("/", <CockpitPage />);

    expect(
      screen.getByRole("region", { name: "Command deck" })
    ).toBeInTheDocument();
    const quick = [
      screen.getByRole("link", { name: "Open table setup" }),
      screen.getByRole("link", { name: "Training lab" }),
      screen.getByRole("link", { name: "Run evaluation" }),
      screen.getByRole("link", { name: "Browse artifacts" }),
    ];
    for (const el of quick) {
      expect(el).toHaveClass("pixel-button", "pixel-button--secondary");
    }
    expect(screen.getByRole("link", { name: "Open table setup" })).toHaveAttribute(
      "href",
      "/play"
    );
    await waitFor(() => {
      expect(screen.getByText("Champion Board")).toBeInTheDocument();
    });
  });

  test("renders new game as a table setup console", () => {
    renderAt("/play", <NewGamePage />);

    expect(
      screen.getByRole("region", { name: "Table setup console" })
    ).toBeInTheDocument();
    expect(screen.getByText("Deal Breaker setup terminal")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Start & open table" })).toHaveClass(
      "pixel-button"
    );
  });

  test("renders lab and artifact index pages with arcade surface headings", async () => {
    vi.mocked(listStrategies).mockResolvedValue({
      built_in: ["basic"],
      neural_prefix: "neural:",
      hint: "Use built-ins or neural checkpoints.",
    });
    vi.mocked(listJobs).mockResolvedValue(emptyList);
    vi.mocked(listCheckpoints).mockResolvedValue(emptyList);
    vi.mocked(listEvaluations).mockResolvedValue(emptyList);
    vi.mocked(listArtifacts).mockResolvedValue(emptyList);

    renderAt("/train", <TrainingLabPage />);
    expect(screen.getByRole("region", { name: "Training console" })).toBeInTheDocument();
    cleanup();

    renderAt("/evaluate", <EvaluationLabPage />);
    expect(
      screen.getByRole("region", { name: "Evaluation console" })
    ).toBeInTheDocument();
    cleanup();

    renderAt("/artifacts", <ArtifactBrowserPage />);
    expect(screen.getByRole("region", { name: "Artifact vault" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByText("No artifacts for this filter.")).toBeInTheDocument();
    });
  });

  test("renders detail and replay pages with shared arcade shells", async () => {
    vi.mocked(getArtifact).mockResolvedValue({
      id: "artifact_1",
      kind: "checkpoint",
      path: "checkpoints/run.pt",
      label: "Run checkpoint",
      metadata: {},
      created_at: "2026-04-27T00:00:00Z",
      imported_at: null,
      links: { download: "/download" },
      job_id: "job_1",
      checkpoint_id: "ckpt_1",
    });
    vi.mocked(getEvaluation).mockResolvedValue({
      id: "eval_1",
      job_id: "job_1",
      candidate: "basic",
      player_count: 2,
      games: 2,
      candidate_score: 1.25,
      promoted: true,
      created_at: "2026-04-27T00:00:00Z",
      links: {},
      baselines: ["basic"],
      seed: 1,
      report: {},
      strategy_scores: { basic: 1.25 },
      promotion_reason: "passed",
    });
    vi.mocked(getCheckpoint).mockResolvedValue({
      id: "ckpt_1",
      path: "checkpoints/run.pt",
      label: "Run checkpoint",
      created_at: "2026-04-27T00:00:00Z",
      links: {},
      player_count: 2,
      strategy_spec: "neural:checkpoints/run.pt",
      promoted: true,
      source_job_id: "job_1",
      schema_version: "1",
      training_stats: {},
      manifest_path: "champions.json",
    });
    vi.mocked(getJob).mockResolvedValue({
      job_id: "job_1",
      kind: "evaluation",
      status: "succeeded",
      config: {},
      result: {},
      error: null,
      log_path: null,
      created_at: "2026-04-27T00:00:00Z",
      started_at: null,
      finished_at: null,
      links: {},
    });
    vi.mocked(getJobLogs).mockResolvedValue({ lines: [], offset: 0, end_offset: 0 });
    vi.mocked(getReplayInspector).mockResolvedValue({
      game_id: "game_1",
      version: 1,
      status: "active",
      replay: { replay_id: "replay_1", step: 0, max_step: 1 },
      legal_actions: [],
      viewer: {
        player_id: "P1",
        hand: [],
        bank: [],
        properties: {},
        actions_taken: 0,
        actions_left: 0,
        discard_required: 0,
      },
      opponents: [],
      deck_count: 12,
      discard_count: 0,
      discard_top: null,
    });

    renderAt("/artifacts/artifact_1", <ArtifactDetailPage />, "/artifacts/:artifactId");
    expect(screen.getByRole("region", { name: "Artifact detail" })).toBeInTheDocument();

    renderAt("/evaluations/eval_1", <EvaluationDetailPage />, "/evaluations/:evaluationId");
    expect(
      screen.getByRole("region", { name: "Evaluation detail" })
    ).toBeInTheDocument();

    renderAt("/jobs/job_1", <JobDetailPage />, "/jobs/:jobId");
    expect(screen.getByRole("region", { name: "Job detail" })).toBeInTheDocument();

    renderAt("/checkpoints/ckpt_1", <CheckpointDetailPage />, "/checkpoints/:checkpointId");
    expect(
      screen.getByRole("region", { name: "Checkpoint detail" })
    ).toBeInTheDocument();

    renderAt("/replays/replay_1", <ReplayInspectorPage />, "/replays/:replayId");
    expect(screen.getByRole("region", { name: "Replay console" })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getAllByText("Run checkpoint").length).toBeGreaterThan(0);
      expect(screen.getByText("Strategy scores")).toBeInTheDocument();
      expect(screen.getByText("Log stream")).toBeInTheDocument();
      expect(screen.getByText("Training telemetry")).toBeInTheDocument();
      expect(screen.getByText("Action step 0 of 1 (version 1)")).toBeInTheDocument();
      expect(screen.getByRole("region", { name: "Prototype play table" })).toBeInTheDocument();
    });
  });

  test("renders live play with arcade shell and developer details", async () => {
    vi.mocked(getGameInspector).mockResolvedValue({
      game_id: "game_z",
      version: 3,
      status: "active",
      turn: 2,
      phase: "action",
      current_player_id: "P1",
      active_player_id: "P1",
      viewer: {
        player_id: "P1",
        hand: [{ id: "c1", name: "Card", kind: "money", value: 1 }],
        bank: [],
        properties: {},
        actions_taken: 0,
        actions_left: 2,
        discard_required: 0,
      },
      opponents: [],
      legal_actions: [],
      deck_count: 40,
      discard_count: 1,
      discard_top: { id: "d1", name: "Discarded", kind: "action", value: 2 },
      timeline: [],
    });

    renderAt("/play/game_z", <PlayInspectorPage />, "/play/:gameId");

    expect(screen.getByRole("region", { name: "Live play console" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Play · game_z", level: 1 })).toBeInTheDocument();

    await waitFor(() => {
      expect(screen.getByRole("region", { name: "Prototype play table" })).toBeInTheDocument();
    });

    expect(screen.getByText("Developer details")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument();
    expect(screen.getByText("Discarded")).toBeInTheDocument();
  });
});
