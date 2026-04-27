/**
 * Route and surface audit for the Deal Breaker web UI.
 *
 * Classifies every routed screen plus global chrome so restyles can target
 * shared primitives (shell, panels, tables) vs. play/replay-specific layouts.
 */

export type SurfaceCategory =
  | "shell"
  | "landing"
  | "play-setup"
  | "play-active"
  | "replay"
  | "lab"
  | "browse"
  | "detail";

export type RouteSurface = {
  readonly path: string;
  readonly page: string;
  readonly category: SurfaceCategory;
  readonly notes: string;
  readonly primaryClasses: readonly string[];
};

/** Global chrome (not a route); wraps all {@link RouteSurface} entries below. */
export const SHELL_SURFACE = {
  component: "AppShell",
  category: "shell" as const,
  notes:
    "Header, primary nav, API/job status strip; uses .app-shell, .shell-header, .brand, .nav, .status-strip.",
  primaryClasses: [
    "app-shell",
    "shell-header",
    "brand",
    "eyebrow",
    "nav",
    "nav-link",
    "status-strip",
    "status-dot",
  ],
};

/**
 * One entry per route in `routes.tsx`, in declaration order.
 * `primaryClasses` lists the main global CSS hooks on that page (not feature-local class names).
 */
export const ROUTE_SURFACE_AUDIT: readonly RouteSurface[] = [
  {
    path: "/",
    page: "CockpitPage",
    category: "landing",
    notes:
      "Command dashboard: quick actions panel, card grid of recent champions/checkpoints/jobs/games/replays/evaluations.",
    primaryClasses: [
      "page-title",
      "panel",
      "cockpit-quick",
      "cockpit-grid",
      "job-item",
      "row",
      "muted",
      "tag",
      "tag--promoted",
    ],
  },
  {
    path: "/play",
    page: "NewGamePage",
    category: "play-setup",
    notes:
      "Game creation form and links into active play; same chrome as labs but copy/actions are play-oriented.",
    primaryClasses: ["page-title", "row", "muted", "error"],
  },
  {
    path: "/play/:gameId",
    page: "PlayInspectorPage",
    category: "play-active",
    notes:
      "1280×720 PlayTable first; card hand popover; session .surface-hero--after-table; dev details in .dev-details.",
    primaryClasses: [
      "play-page",
      "page-title",
      "surface-hero--after-table",
      "dev-details",
      "muted",
      "error",
    ],
  },
  {
    path: "/replays/:replayId",
    page: "ReplayInspectorPage",
    category: "replay",
    notes:
      "Step controls and status, read-only PlayTable, compact hero, inspector details drawer.",
    primaryClasses: [
      "replay-console",
      "page-title",
      "surface-hero--after-table",
      "dev-details",
      "muted",
      "error",
    ],
  },
  {
    path: "/train",
    page: "TrainingLabPage",
    category: "lab",
    notes:
      "Training / RL / import forms, two-column layout, job and checkpoint lists.",
    primaryClasses: [
      "page-title",
      "layout-two",
      "panel",
      "form-stack",
      "row",
      "job-item",
      "muted",
      "tag",
      "error",
    ],
  },
  {
    path: "/evaluate",
    page: "EvaluationLabPage",
    category: "lab",
    notes: "Evaluation runner form, job list, persisted evaluation list.",
    primaryClasses: [
      "page-title",
      "panel",
      "form-stack",
      "checkbox-row",
      "layout-two",
      "job-item",
      "muted",
      "tag",
      "error",
    ],
  },
  {
    path: "/evaluations/:evaluationId",
    page: "EvaluationDetailPage",
    category: "detail",
    notes: "Summary panel, results data-table, raw JSON.",
    primaryClasses: [
      "page-title",
      "panel",
      "detail-dl",
      "data-table",
      "tag",
      "tag--promoted",
      "tag--muted",
      "inspector-raw",
      "muted",
      "error",
    ],
  },
  {
    path: "/artifacts",
    page: "ArtifactBrowserPage",
    category: "browse",
    notes: "Filtered list of artifacts; rows reuse .job-item pattern.",
    primaryClasses: ["page-title", "panel", "row", "job-item", "tag", "muted", "error"],
  },
  {
    path: "/artifacts/:artifactId",
    page: "ArtifactDetailPage",
    category: "detail",
    notes: "Metadata panel, optional actions row, raw inspector JSON.",
    primaryClasses: [
      "page-title",
      "panel",
      "detail-dl",
      "row",
      "inspector-raw",
      "tag",
      "muted",
      "error",
    ],
  },
  {
    path: "/checkpoints/:checkpointId",
    page: "CheckpointDetailPage",
    category: "detail",
    notes: "Checkpoint metadata, links, raw JSON.",
    primaryClasses: [
      "page-title",
      "panel",
      "detail-dl",
      "row",
      "inspector-raw",
      "tag",
      "tag--promoted",
      "muted",
      "error",
    ],
  },
  {
    path: "/jobs/:jobId",
    page: "JobDetailPage",
    category: "detail",
    notes: "Job status, error, config JSON, log-viewer panel.",
    primaryClasses: [
      "page-title",
      "panel",
      "inspector-raw",
      "inspector-raw--tight",
      "log-viewer",
      "muted",
      "error",
    ],
  },
];

/** Feature folders that implement play/replay-specific UI (not routed themselves). */
export const PLAY_FEATURE_AREAS = {
  inspector: {
    path: "web/src/features/inspector",
    notes:
      "BoardState, LegalActionPanel, timelines, chips — shared between Play and Replay; restyle affects both until split.",
  },
} as const;
