import type {
  AiStepRequest,
  AiStepResponse,
  ArtifactDetail,
  ArtifactImportJobRequest,
  ArtifactListItem,
  CheckpointDetail,
  CheckpointListItem,
  EvalJobRequest,
  EvaluationDetail,
  EvaluationListItem,
  GameActionRequest,
  GameActionResponse,
  GameListItem,
  HealthResponse,
  Inspector,
  JobCreatedResponse,
  JobDetail,
  ListResponse,
  LogSliceResponse,
  NewGameRequest,
  NewGameResponse,
  ReplayLinkResponse,
  ReplayListItem,
  RlSearchJobRequest,
  StrategiesResponse,
  TournamentJobRequest,
  TrainingJobRequest,
} from "./types";

export type { Inspector } from "./types";

const API = "/api";

async function j<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`HTTP ${res.status}: ${text || res.statusText}`);
  }
  return (await res.json()) as T;
}

function apiUrl(path: string, params?: Record<string, string | number | null | undefined>): string {
  const q = new URLSearchParams();
  Object.entries(params ?? {}).forEach(([key, value]) => {
    if (value != null) q.set(key, String(value));
  });
  const query = q.toString();
  return `${API}${path}${query ? `?${query}` : ""}`;
}

async function postJson<TResponse, TBody>(path: string, body: TBody): Promise<TResponse> {
  return j(
    await fetch(apiUrl(path), {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    })
  );
}

export async function getHealth(): Promise<HealthResponse> {
  return j(await fetch(`${API}/health`));
}

export async function newGame(body: NewGameRequest): Promise<NewGameResponse> {
  return postJson("/games", body);
}

export async function getGameInspector(
  gameId: string,
  viewer: string
): Promise<Inspector> {
  const q = new URLSearchParams({ viewer });
  return j(await fetch(`${API}/games/${encodeURIComponent(gameId)}/inspector?${q}`));
}

export async function postAction(
  gameId: string,
  body: GameActionRequest
): Promise<GameActionResponse> {
  return postJson(`/games/${encodeURIComponent(gameId)}/actions`, body);
}

export async function postAiStep(
  gameId: string,
  body: AiStepRequest
): Promise<AiStepResponse> {
  return postJson(`/games/${encodeURIComponent(gameId)}/ai-step`, body);
}

export async function getReplayInspector(
  replayId: string,
  step: number,
  viewer: string
): Promise<Inspector> {
  const q = new URLSearchParams({ step: String(step), viewer });
  return j(
    await fetch(
      `${API}/replays/${encodeURIComponent(replayId)}/inspector?${q}`
    )
  );
}

export async function listJobs(params?: {
  limit?: number;
  offset?: number;
  kind?: string;
  status?: string;
}): Promise<ListResponse<JobDetail>> {
  return j(await fetch(apiUrl("/jobs", params)));
}

export async function getJob(jobId: string): Promise<JobDetail> {
  return j(await fetch(`${API}/jobs/${encodeURIComponent(jobId)}`));
}

export async function startEval(body: EvalJobRequest): Promise<JobCreatedResponse> {
  return postJson("/jobs/evaluations", body);
}

export async function startTraining(
  body: TrainingJobRequest
): Promise<JobCreatedResponse> {
  return postJson("/jobs/training", body);
}

export async function replayLink(gameId: string): Promise<ReplayLinkResponse> {
  return j(
    await fetch(
      `${API}/sessions/${encodeURIComponent(gameId)}/replay-link`
    )
  );
}

export async function listGames(params?: {
  limit?: number;
  offset?: number;
  status?: string;
}): Promise<ListResponse<GameListItem>> {
  return j(await fetch(apiUrl("/games", params)));
}

export async function listReplays(params?: {
  limit?: number;
  offset?: number;
}): Promise<ListResponse<ReplayListItem>> {
  return j(await fetch(apiUrl("/replays", params)));
}

export async function listCheckpoints(params?: {
  limit?: number;
  offset?: number;
  player_count?: number;
}): Promise<ListResponse<CheckpointListItem>> {
  return j(await fetch(apiUrl("/checkpoints", params)));
}

export async function listEvaluations(params?: {
  limit?: number;
  offset?: number;
}): Promise<ListResponse<EvaluationListItem>> {
  return j(await fetch(apiUrl("/evaluations", params)));
}

export async function listArtifacts(params?: {
  limit?: number;
  offset?: number;
  kind?: string;
}): Promise<ListResponse<ArtifactListItem>> {
  return j(await fetch(apiUrl("/artifacts", params)));
}

export async function getCheckpoint(checkpointId: string): Promise<CheckpointDetail> {
  return j(
    await fetch(`${API}/checkpoints/${encodeURIComponent(checkpointId)}`)
  );
}

export async function getEvaluation(evaluationId: string): Promise<EvaluationDetail> {
  return j(
    await fetch(`${API}/evaluations/${encodeURIComponent(evaluationId)}`)
  );
}

export async function getArtifact(artifactId: string): Promise<ArtifactDetail> {
  return j(await fetch(`${API}/artifacts/${encodeURIComponent(artifactId)}`));
}

export async function listChampions(): Promise<ListResponse<CheckpointListItem>> {
  return j(await fetch(`${API}/champions`));
}

export async function listStrategies(): Promise<StrategiesResponse> {
  return j(await fetch(`${API}/strategies`));
}

export async function getJobLogs(
  jobId: string,
  params?: { offset?: number; limit?: number }
): Promise<LogSliceResponse> {
  return j(
    await fetch(apiUrl(`/jobs/${encodeURIComponent(jobId)}/logs`, params))
  );
}

export async function startRlSearch(
  body: RlSearchJobRequest
): Promise<JobCreatedResponse> {
  return postJson("/jobs/rl-search", body);
}

export async function startTournament(
  body: TournamentJobRequest
): Promise<JobCreatedResponse> {
  return postJson("/jobs/tournament", body);
}

export async function startArtifactImport(
  body: ArtifactImportJobRequest
): Promise<JobCreatedResponse> {
  return postJson("/jobs/artifact-import", body);
}
