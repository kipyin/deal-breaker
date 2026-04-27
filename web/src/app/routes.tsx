import { Navigate, type RouteObject } from "react-router-dom";
// Surface classification for restyle work: see ./routeSurfaces.ts
import { AppShell } from "./AppShell";
import { ArtifactBrowserPage } from "../pages/ArtifactBrowserPage";
import { ArtifactDetailPage } from "../pages/ArtifactDetailPage";
import { CheckpointDetailPage } from "../pages/CheckpointDetailPage";
import { CockpitPage } from "../pages/CockpitPage";
import { EvaluationDetailPage } from "../pages/EvaluationDetailPage";
import { EvaluationLabPage } from "../pages/EvaluationLabPage";
import { JobDetailPage } from "../pages/JobDetailPage";
import { NewGamePage } from "../pages/NewGamePage";
import { PlayInspectorPage } from "../pages/PlayInspectorPage";
import { ReplayInspectorPage } from "../pages/ReplayInspectorPage";
import { TrainingLabPage } from "../pages/TrainingLabPage";

export const appRoutes: RouteObject[] = [
  {
    element: <AppShell />,
    children: [
      { index: true, element: <CockpitPage /> },
      { path: "play", element: <NewGamePage /> },
      { path: "play/:gameId", element: <PlayInspectorPage /> },
      { path: "replays/:replayId", element: <ReplayInspectorPage /> },
      { path: "train", element: <TrainingLabPage /> },
      { path: "evaluate", element: <EvaluationLabPage /> },
      { path: "evaluations/:evaluationId", element: <EvaluationDetailPage /> },
      { path: "artifacts", element: <ArtifactBrowserPage /> },
      { path: "artifacts/:artifactId", element: <ArtifactDetailPage /> },
      { path: "checkpoints/:checkpointId", element: <CheckpointDetailPage /> },
      { path: "jobs/:jobId", element: <JobDetailPage /> },
      { path: "*", element: <Navigate replace to="/" /> },
    ],
  },
];
