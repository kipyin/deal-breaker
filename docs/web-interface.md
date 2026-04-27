# Web Interface Architecture

This document defines the first production-style web boundary for Deal Breaker.
It is intentionally thin: the web layer adapts existing engine, strategy,
training, evaluation, and replay modules instead of reimplementing game rules.

## Backend Service Boundaries

Add backend code under `src/dbreaker/web` with these internal service modules:

- `game_service.py` owns live browser play sessions. It creates `Game` instances
  with `Game.new`, asks `game.legal_actions(player_id)` for the action menu,
  applies user or AI turns with `game.step`, and builds UI state from
  `game.observation_for`. It may use `dbreaker.cli.commands.legal_action_for_command`
  only as a compatibility adapter for CLI-style shortcut strings; structured web
  actions should use `dbreaker.engine.actions.action_from_payload`.
- `inspector_service.py` owns read-only state projection for live games and replay
  logs. It converts `Observation`, `Game.event_log`, and `Game.action_log` into
  stable JSON, delegates event filtering to `dbreaker.replay.inspector`, and never
  mutates game state.
- `strategy_service.py` owns strategy lookup and AI decisions. It wraps
  `dbreaker.strategies.registry.create_strategy`, supports built-in names and
  `neural:<checkpoint>` specs, and returns decision metadata without exposing
  strategy internals to routes.
- `job_service.py` owns durable local jobs and log capture. It schedules training,
  RL search, evaluation, benchmark, and import jobs, records status transitions in
  SQLite, writes append-only job logs under the artifact root, and runs job
  handlers in a local background worker for v1.
- `training_service.py` adapts `PPOConfig`, `train_self_play`, and `run_rl_search`
  for web-triggered training. It creates checkpoint and manifest paths, passes
  validated config into existing ML functions, and records returned
  `TrainingStats` without adding an alternate training loop.
- `evaluation_service.py` adapts `EvaluationConfig`, `evaluate_candidate`,
  `promote_champion`, and `run_tournament`. It records tournament summaries,
  guardrail decisions, strategy scores, and promotion results.
- `artifact_service.py` indexes existing and newly-created files under the
  artifact root: `.pt` checkpoints, RL search manifests, champions manifests,
  replay JSONL files, job logs, and imported metadata.

FastAPI routes should remain small. They validate requests, call one service, and
serialize the result. Game rules stay in `dbreaker.engine`, strategy behavior
stays in `dbreaker.strategies`, and long-running ML/evaluation behavior stays in
`dbreaker.ml` and `dbreaker.experiments`.

## SQLite Metadata Model

Use one SQLite database under the configurable data root:

```text
<data_root>/dbreaker.sqlite3
```

Recommended default roots:

```text
.dbreaker/
  dbreaker.sqlite3
  artifacts/
    checkpoints/
    replays/
    jobs/
    evaluations/
    imports/
```

The database stores metadata and compact summaries. Large artifacts remain files.

```sql
create table schema_migrations (
  version text primary key,
  applied_at text not null
);

create table jobs (
  id text primary key,
  kind text not null check (kind in (
    'play_session',
    'training',
    'rl_search',
    'evaluation',
    'tournament',
    'artifact_import'
  )),
  status text not null check (status in (
    'queued',
    'running',
    'succeeded',
    'failed',
    'cancelled'
  )),
  config_json text not null,
  result_json text,
  error text,
  log_path text,
  created_at text not null,
  started_at text,
  finished_at text,
  updated_at text not null
);

create table games (
  id text primary key,
  source text not null check (source in ('live', 'scripted', 'self_play', 'imported')),
  job_id text references jobs(id),
  player_count integer not null,
  seed integer,
  strategy_specs_json text not null,
  status text not null check (status in ('active', 'completed', 'aborted')),
  winner_id text,
  ended_by text,
  turn_count integer not null default 0,
  replay_path text,
  action_log_json text,
  created_at text not null,
  finished_at text
);

create table replays (
  id text primary key,
  game_id text references games(id),
  path text not null unique,
  event_count integer not null default 0,
  first_turn integer,
  last_turn integer,
  imported_at text not null,
  metadata_json text not null
);

create table checkpoints (
  id text primary key,
  path text not null unique,
  label text,
  player_count integer,
  source_job_id text references jobs(id),
  schema_version text,
  strategy_spec text not null,
  training_stats_json text not null,
  manifest_path text,
  promoted boolean not null default 0,
  created_at text not null
);

create table evaluations (
  id text primary key,
  job_id text references jobs(id),
  candidate_spec text not null,
  player_count integer not null,
  baselines_json text not null,
  games integer not null,
  seed integer not null,
  report_json text not null,
  candidate_score real not null,
  strategy_scores_json text not null,
  promoted boolean,
  promotion_reason text,
  created_at text not null
);

create table metric_summaries (
  id text primary key,
  subject_type text not null check (subject_type in ('job', 'game', 'checkpoint', 'evaluation')),
  subject_id text not null,
  name text not null,
  value real not null,
  unit text,
  metadata_json text not null,
  created_at text not null
);

create index jobs_status_created_at on jobs(status, created_at);
create index games_job_id on games(job_id);
create index replays_game_id on replays(game_id);
create index checkpoints_player_count on checkpoints(player_count);
create index evaluations_candidate_spec on evaluations(candidate_spec);
create index metric_summaries_subject on metric_summaries(subject_type, subject_id);
```

Artifact paths stored in SQLite should be relative to the artifact root when
possible. This keeps the database portable across machines and deploy targets.

Use deterministic artifact locations:

```text
artifacts/jobs/<job_id>/log.txt
artifacts/jobs/<job_id>/result.json
artifacts/replays/<game_id>.jsonl
artifacts/checkpoints/<player_count>p/<checkpoint_id>.pt
artifacts/checkpoints/<player_count>p/<checkpoint_id>.json
artifacts/evaluations/<evaluation_id>/report.json
artifacts/imports/<import_batch_id>/<original_relative_path>
```

Existing files under `checkpoints/rl-search/<Np>/run-NNN.{pt,json}` should be
imported as checkpoint rows plus manifest metadata, not moved by default.

## FastAPI JSON Contracts

All API responses use `application/json`. Timestamps are ISO-8601 UTC strings.
Route handlers should return `400` for invalid user input, `404` for unknown IDs,
`409` for stale game versions or illegal state transitions, and `500` only for
unexpected server failures.

### Shared Shapes

```json
{
  "Card": {
    "id": "blue-1",
    "name": "Boardwalk",
    "kind": "property",
    "value": 4,
    "color": "blue",
    "colors": [],
    "action_subtype": null
  },
  "Action": {
    "id": "a_0001",
    "label": "Bank Boardwalk",
    "payload": {
      "type": "BankCard",
      "card_id": "blue-1"
    },
    "shortcut": "bank blue-1"
  },
  "Event": {
    "index": 12,
    "type": "bank",
    "turn": 3,
    "player": "P1",
    "action": "BankCard",
    "target": null,
    "card": "blue-1",
    "result": "accepted",
    "reason_summary": "P1 banked Boardwalk",
    "payload": {}
  }
}
```

### Inspector State

`GET /api/games/{game_id}/inspector?viewer=P1&omniscient=false`

```json
{
  "game_id": "game_01HY",
  "version": 7,
  "status": "active",
  "turn": 3,
  "phase": "action",
  "current_player_id": "P1",
  "active_player_id": "P1",
  "winner_id": null,
  "viewer": {
    "player_id": "P1",
    "hand": [],
    "bank": [],
    "properties": {},
    "actions_taken": 1,
    "actions_left": 2,
    "discard_required": 0
  },
  "opponents": [
    {
      "id": "P2",
      "name": "P2",
      "hand_size": 5,
      "bank": [],
      "bank_value": 0,
      "properties": {},
      "completed_sets": 0
    }
  ],
  "pending": null,
  "legal_actions": [],
  "timeline": [],
  "last_action": null
}
```

The backend builds this from `Observation`, legal actions from `Game.legal_actions`,
events from `Game.event_log`, and action digests from `Game.action_log`.

### Play Actions

`POST /api/games`

```json
{
  "player_count": 3,
  "human_player_id": "P1",
  "ai_strategy": "basic",
  "seed": 42
}
```

Response:

```json
{
  "game_id": "game_01HY",
  "version": 0,
  "inspector": {}
}
```

`POST /api/games/{game_id}/actions`

```json
{
  "player_id": "P1",
  "expected_version": 7,
  "action": {
    "type": "BankCard",
    "card_id": "blue-1"
  }
}
```

Response:

```json
{
  "game_id": "game_01HY",
  "version": 8,
  "accepted": true,
  "events": [],
  "inspector": {}
}
```

`POST /api/games/{game_id}/ai-step`

```json
{
  "expected_version": 8,
  "max_steps": 10
}
```

This advances AI-controlled turns until the next human decision, terminal state,
or `max_steps` cap.

### Training Jobs

`POST /api/jobs/training`

```json
{
  "player_count": 4,
  "games": 20,
  "seed": 1,
  "max_turns": 200,
  "max_self_play_steps": 30000,
  "update_epochs": 2,
  "gamma": 0.99,
  "opponent_mix_prob": 0.0,
  "opponent_strategies": ["basic", "aggressive", "defensive", "set_completion"],
  "champion_checkpoint_id": null,
  "checkpoint_label": "4p-smoke"
}
```

Response:

```json
{
  "job_id": "job_train_01HY",
  "status": "queued",
  "links": {
    "self": "/api/jobs/job_train_01HY",
    "logs": "/api/jobs/job_train_01HY/logs"
  }
}
```

`GET /api/jobs/{job_id}`

```json
{
  "job_id": "job_train_01HY",
  "kind": "training",
  "status": "running",
  "config": {},
  "result": null,
  "error": null,
  "created_at": "2026-04-27T03:15:00Z",
  "started_at": "2026-04-27T03:15:02Z",
  "finished_at": null,
  "links": {
    "logs": "/api/jobs/job_train_01HY/logs"
  }
}
```

`GET /api/jobs/{job_id}/logs?offset=0&limit=200` returns ordered log lines with
their byte offset so the UI can poll incrementally without rereading the whole
file.

`POST /api/jobs/rl-search` uses the same fields plus `player_counts` and
`runs_per_count`, then delegates to `run_rl_search`.

### Evaluation Jobs

`POST /api/jobs/evaluations`

```json
{
  "candidate": "neural:artifacts/checkpoints/4p/ckpt_01HY.pt",
  "player_count": 4,
  "baselines": ["basic", "aggressive", "defensive", "set_completion"],
  "games": 20,
  "seed": 1,
  "max_turns": 200,
  "max_self_play_steps": 30000,
  "champions_manifest_path": "artifacts/checkpoints/champions.json",
  "promote_if_passes": false,
  "max_aborted_rate": 0.0
}
```

Responses follow the common job envelope. Completed evaluation jobs expose
`EvaluationResult` fields as `result_json`: report summary, candidate score,
strategy scores, outcome rates, and promotion decision.

### Artifact Browsing

`GET /api/artifacts?kind=checkpoint&player_count=4&limit=50`

```json
{
  "items": [
    {
      "id": "ckpt_01HY",
      "kind": "checkpoint",
      "path": "artifacts/checkpoints/4p/ckpt_01HY.pt",
      "label": "4p-smoke",
      "created_at": "2026-04-27T03:15:00Z",
      "metadata": {
        "player_count": 4,
        "strategy_spec": "neural:artifacts/checkpoints/4p/ckpt_01HY.pt",
        "training_stats": {}
      }
    }
  ],
  "next_cursor": null
}
```

`GET /api/artifacts/{artifact_id}` returns metadata only. File downloads, when
enabled, should require an explicit route such as
`GET /api/artifacts/{artifact_id}/download` to keep the UI from accidentally
pulling large checkpoints.

## React App Shell

Create the frontend under `web/` with Vite, React, and TypeScript. The frontend
should treat the FastAPI backend as the source of truth and keep only ephemeral UI
state locally.

Recommended route tree:

```text
/
  CockpitPage
/play
  NewGamePage
/games/:gameId
  PlayInspectorPage
/replays/:replayId
  ReplayInspectorPage
/train
  TrainingLabPage
/train/jobs/:jobId
  JobDetailPage
/evaluate
  EvaluationLabPage
/evaluate/:evaluationId
  EvaluationDetailPage
/artifacts
  ArtifactBrowserPage
/artifacts/:artifactId
  ArtifactDetailPage
/settings
  SettingsPage
```

Shell layout:

- `AppShell` provides top navigation, data-root/backend status, and a persistent
  job activity indicator.
- `CockpitPage` shows current champions/checkpoints, recent jobs, recent games,
  latest evaluation summaries, and quick actions for play, train, evaluate, and
  inspect.
- `PlayInspectorPage` combines the play surface and inspector. The play surface
  uses a striped pixel table: opponents around the board, draw/discard piles and
  actions-left in the center, player bank/properties on the table, and a curved
  hand dock with card-specific context menus. The inspector column shows timeline,
  event details, AI decisions, and raw action payloads.
- `ReplayInspectorPage` reuses inspector components with step-through controls,
  event filters, and immutable replay metadata.
- `TrainingLabPage` contains a job creation form, active job list, logs preview,
  completed run comparison, and checkpoint promotion shortcuts.
- `EvaluationLabPage` starts candidate-vs-baseline jobs and displays compact
  win-rate, rating, average-rank, outcome-rate, and promotion-guardrail cards.
- `ArtifactBrowserPage` filters checkpoints, manifests, replays, logs, and
  evaluation reports by kind, player count, source, and created time.

Suggested component boundaries:

```text
web/src/app/AppShell.tsx
web/src/app/routes.tsx
web/src/api/client.ts
web/src/api/types.ts
web/src/features/cockpit/CockpitPage.tsx
web/src/features/inspector/BoardState.tsx
web/src/features/inspector/LegalActionPanel.tsx
web/src/features/inspector/EventTimeline.tsx
web/src/features/play/PlayInspectorPage.tsx
web/src/features/train/TrainingLabPage.tsx
web/src/features/evaluate/EvaluationLabPage.tsx
web/src/features/artifacts/ArtifactBrowserPage.tsx
web/src/features/jobs/JobDetailPage.tsx
```

Navigation should start with:

```text
Cockpit | Play | Train | Evaluate | Artifacts
```

Keep admin-like actions, such as training and promotion, behind component-level
permission checks even though v1 has no auth. This gives the future backend a
single place to enforce the same protection.

## Verification

From the repository root (with the `dev` extra: `uv sync --extra dev`):

```bash
# Full local app: starts FastAPI and Vite, then opens the frontend.
uv run dbreaker web

# Automation-friendly full app launch (prints URLs without opening a browser).
uv run dbreaker web --no-open

# Backend-only API service for API testing or custom frontend workflows.
uv run dbreaker api

# Backend API tests for the web stack
uv run pytest tests/web

# Style
uv run ruff check .

# Static typing (strict on `src/dbreaker/web`; see `pyproject.toml`)
uv run mypy
```

From `web/` (after `npm install`):

```bash
npm run typecheck
npm test
npm run build
```

### Play table layout (manual visual regression)

Automated `vitest` + jsdom tests cover `PlayTable` content, actions, and the
required `Card table`, `Board center`, `Board controls`, `Opponent seats`, and
`Hand dock` landmarks. They cannot assert pixel overlap on the arcade felt, so
after CSS or layout changes to the play surface, open **Play** in the dev app and
spot-check the following. Resize the browser between checks.

| State | What to verify |
| --- | --- |
| **Normal** | Default mid-game view (few hand cards, typical bank/properties). Opponents sit above/around the board, draw/discard piles and the actions-left badge sit in the center, and **END TURN** stays in board controls. |
| **Dense** | Stress-test hands and long copy. The hand remains fanned for small hands and becomes flatter/scrollable for dense hands; selected-card menus stay reachable above the clicked card. |
| **Medium / small** | Around **760-900px**, then narrower mobile widths. Opponents collapse into a simpler rail, board center stacks above bank/properties, and the hand dock remains usable. |
| **Large** | About **1280x720** (or max frame). The surface reads as a single striped card table, not a dashboard: fewer boxes, centered piles, visible opponent summaries, curved hand. |
| **Selected card** | Select a hand card. Its context menu appears above that card with legal plays, **View card details**, and **Cancel**. `View card details` opens a centered dimmed overlay. |
| **Opponent details** | Click an opponent bank block to inspect public bank cards. Click the property graph to inspect property cards. Opponent hands remain hidden except for `hand_size`. |
| **Flash / pending** | Trigger a `flashMessage` and a pending response. The alert, pending summary, last action, and primary action remain in board controls without recreating the old action-zone panel. |

Related classes and tokens: `play-board`, `board-center`, `board-controls`,
`play-opponents` (`data-opponent-count`), `player-area__hand-rail`,
`play-hand` (`data-hand-count`, `data-hand-dense`), `card-action-panel`,
`card-detail`, and `opponent-detail` in
`web/src/styles/07-active-play-surface.css`. Keep
`web/src/features/play/PlayTable.test.tsx` passing and extend it when adding new
required landmarks or card-table states.

For local UI development, `uv run dbreaker web` is the default one-command launcher.
It serves the API on `http://127.0.0.1:8765` and the Vite frontend on
`http://127.0.0.1:5173`; the frontend proxies `/api` to the backend. Use
`uv run dbreaker api` when you only want the FastAPI service.
