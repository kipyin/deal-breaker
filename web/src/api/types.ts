export type JsonPrimitive = string | number | boolean | null;
export type JsonValue = JsonPrimitive | JsonObject | JsonValue[];
export type JsonObject = { [key: string]: JsonValue };

export type LinkMap = Record<string, string>;

export interface HealthResponse {
  status: string;
}

export type JobStatus =
  | "queued"
  | "running"
  | "succeeded"
  | "failed"
  | "cancelled";

export type JobKind =
  | "evaluation"
  | "training"
  | "rl_search"
  | "tournament"
  | "artifact_import";

export interface JobDetail {
  job_id: string;
  kind: JobKind | string;
  status: JobStatus | string;
  config: JsonObject;
  result: JsonObject | null;
  error: string | null;
  log_path: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  links: LinkMap;
}

export interface ListResponse<T> {
  items: T[];
  next_cursor?: string | null;
}

export type Inspector = JsonObject & {
  version?: number;
  status?: string;
  legal_actions?: LegalAction[];
  replay?: ReplayInspectorMeta;
};

/** Structured game inspector payload from `build_inspector_state` (live or replay). */
export interface InspectorTimelineEvent {
  index?: number;
  type?: string;
  turn?: number;
  player?: string | null;
  action?: string | null;
  target?: string | null;
  card?: string | null;
  result?: string | null;
  reason_summary?: string;
  debug_reasoning?: string | null;
  payload?: JsonObject;
}

export interface InspectorCard {
  id?: string;
  name?: string;
  kind?: string;
  value?: number;
  color?: string | null;
  colors?: string[];
  action_subtype?: string | null;
}

export interface InspectorViewer {
  player_id: string;
  hand: InspectorCard[];
  bank: InspectorCard[];
  properties: Record<string, InspectorCard[]>;
  actions_taken: number;
  actions_left: number;
  discard_required: number;
}

export interface InspectorOpponent {
  id: string;
  name: string;
  hand_size: number;
  bank_value: number;
  properties: Record<string, InspectorCard[]>;
  completed_sets: number;
}

export interface InspectorPending {
  kind: string;
  actor_id: string;
  target_id: string;
  respond_player_id: string | null;
  amount: number;
  source_card_name: string;
  reason: string;
  negated: boolean;
}

export interface InspectorLastAction {
  player_id: string;
  payload: JsonObject;
}

export interface InspectorState {
  game_id: string;
  version?: number;
  status?: string;
  turn?: number;
  phase?: string;
  current_player_id?: string;
  active_player_id?: string;
  winner_id?: string | null;
  viewer?: InspectorViewer;
  opponents?: InspectorOpponent[];
  pending?: InspectorPending | null;
  legal_actions?: LegalAction[];
  timeline?: InspectorTimelineEvent[];
  last_action?: InspectorLastAction | null;
  /** Cards remaining in the draw pile (live engine state). */
  deck_count?: number;
  /** Cards in the discard pile. */
  discard_count?: number;
  /** Top card on the discard pile, or null if empty. */
  discard_top?: InspectorCard | null;
  replay?: ReplayInspectorMeta;
}

export interface LegalAction {
  id: string;
  label: string;
  payload: JsonObject;
}

export interface ReplayInspectorMeta {
  replay_id: string;
  max_step: number;
  step: number;
}

export interface NewGameRequest {
  player_count: number;
  human_player_id?: string;
  ai_strategy?: string;
  seed?: number | null;
}

export interface NewGameResponse {
  game_id: string;
  version: number;
  inspector: Inspector;
}

export interface GameActionRequest {
  player_id: string;
  expected_version: number;
  action: JsonObject;
}

export interface GameActionResponse {
  version: number;
  accepted: boolean;
  events: JsonValue[];
  inspector: Inspector;
}

export interface AiStepRequest {
  expected_version: number;
  max_steps?: number;
}

export interface AiStepResponse {
  version: number;
  done: string;
  steps_run: number;
  inspector: Inspector;
}

export interface EvalJobRequest {
  candidate: string;
  player_count: number;
  baselines: string[];
  games: number;
  seed?: number;
  max_turns?: number;
  max_self_play_steps?: number;
  champions_manifest_path?: string | null;
  promote_if_passes?: boolean;
  max_aborted_rate?: number;
}

export interface TrainingJobRequest {
  player_count: number;
  games?: number;
  seed?: number;
  max_turns?: number;
  max_self_play_steps?: number;
  update_epochs?: number;
  gamma?: number;
  learning_rate?: number;
  clip_epsilon?: number;
  value_coef?: number;
  entropy_coef?: number;
  opponent_mix_prob?: number;
  opponent_strategies?: string[];
  champion_checkpoint_id?: string | null;
  checkpoint_label?: string | null;
}

export interface JobCreatedResponse {
  job_id: string;
  status: JobStatus | string;
  links?: LinkMap;
}

export interface GameListItem {
  game_id: string;
  source: string;
  job_id: string | null;
  player_count: number;
  seed: number | null;
  status: string;
  winner_id: string | null;
  turn_count: number;
  replay_path: string | null;
  created_at: string;
  finished_at: string | null;
  links: LinkMap;
}

export interface ReplayListItem {
  replay_id: string;
  game_id: string;
  path: string;
  event_count: number;
  imported_at: string;
  metadata: JsonObject;
  links: LinkMap;
}

export interface CheckpointListItem {
  id: string;
  path: string;
  label: string | null;
  player_count: number | null;
  strategy_spec: string;
  promoted: boolean;
  created_at: string;
  links: LinkMap;
}

export interface ArtifactListItem {
  id: string;
  kind: string;
  path: string;
  label: string | null;
  metadata: JsonObject;
  created_at: string;
  imported_at: string | null;
  links: LinkMap;
}

export interface EvaluationListItem {
  id: string;
  job_id: string | null;
  candidate: string;
  player_count: number;
  games: number;
  candidate_score: number;
  promoted: boolean | null;
  created_at: string;
  links: LinkMap;
}

/** Full checkpoint row from `GET /api/checkpoints/:id`. */
export interface CheckpointDetail extends CheckpointListItem {
  source_job_id: string | null;
  schema_version: string | null;
  training_stats: JsonObject;
  manifest_path: string | null;
}

export interface EvaluationDetail extends EvaluationListItem {
  baselines: string[];
  seed: number;
  report: JsonObject;
  strategy_scores: Record<string, number>;
  promotion_reason: string | null;
}

export interface ArtifactDetail extends ArtifactListItem {
  job_id: string | null;
  checkpoint_id: string | null;
}

export interface StrategiesResponse {
  built_in: string[];
  neural_prefix: string;
  hint: string;
}

export interface RlSearchJobRequest {
  player_counts: number[];
  runs_per_count?: number;
  games_per_run?: number;
  seed?: number;
  max_turns?: number;
  max_self_play_steps?: number;
  update_epochs?: number;
  gamma?: number;
  opponent_mix_prob?: number;
  opponent_strategies?: string[];
  champion_checkpoint_id?: string | null;
}

export interface TournamentJobRequest {
  player_count: number;
  games?: number;
  strategies: string[];
  seed?: number;
  max_turns?: number;
  max_self_play_steps?: number;
}

export interface ArtifactImportJobRequest {
  rel_path: string;
}

export interface LogSliceResponse {
  lines: string[];
  offset: number;
  end_offset: number;
}

export interface ReplayLinkResponse {
  replay_id: string | null;
}
