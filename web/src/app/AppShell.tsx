import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { getHealth, listJobs } from "../api/client";
import type { JobDetail } from "../api/types";

const activeStatuses = new Set(["queued", "running"]);

const navItems = [
  { label: "Cockpit", to: "/" },
  { label: "Play", to: "/play" },
  { label: "Train", to: "/train" },
  { label: "Evaluate", to: "/evaluate" },
  { label: "Artifacts", to: "/artifacts" },
];

function pluralize(count: number, singular: string): string {
  return `${count} ${singular}${count === 1 ? "" : "s"}`;
}

function StatusStrip() {
  const [apiStatus, setApiStatus] = useState<"loading" | string>("loading");
  const [jobs, setJobs] = useState<JobDetail[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function refreshStatus() {
      try {
        const [health, recentJobs] = await Promise.all([
          getHealth(),
          listJobs({ limit: 10 }),
        ]);
        if (cancelled) return;
        setApiStatus(health.status);
        setJobs(recentJobs.items);
        setError(null);
      } catch (e) {
        if (cancelled) return;
        setApiStatus("offline");
        setError(e instanceof Error ? e.message : String(e));
      }
    }

    void refreshStatus();
    const timer = window.setInterval(() => void refreshStatus(), 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const activeJobCount = useMemo(
    () => jobs.filter((job) => activeStatuses.has(job.status)).length,
    [jobs]
  );

  return (
    <div
      aria-label="Backend status"
      className="status-strip"
      role="status"
      title={error ?? undefined}
    >
      <span className={`status-dot ${error ? "status-dot--error" : ""}`} />
      <span>API {apiStatus}</span>
      <span>{pluralize(activeJobCount, "active job")}</span>
      {jobs[0] && (
        <span className="status-strip__latest">
          Latest {jobs[0].kind}: {jobs[0].status}
        </span>
      )}
    </div>
  );
}

export function AppShell() {
  return (
    <div className="app-shell">
      <header className="shell-header">
        <div>
          <p className="eyebrow">Deal Breaker Lab</p>
          <div className="brand">DEAL BREAKER</div>
        </div>
        <StatusStrip />
      </header>
      <nav aria-label="Primary" className="nav">
        {navItems.map((item) => (
          <NavLink
            className={({ isActive }) => (isActive ? "nav-link active" : "nav-link")}
            end={item.to === "/"}
            key={item.to}
            to={item.to}
          >
            {item.label}
          </NavLink>
        ))}
      </nav>
      <main className="page-surface">
        <Outlet />
      </main>
    </div>
  );
}
