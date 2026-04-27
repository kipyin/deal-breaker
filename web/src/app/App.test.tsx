import { render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, describe, expect, test, vi } from "vitest";
import { App } from "../App";
import { getHealth, listJobs } from "../api/client";

vi.mock("../api/client", async (importOriginal) => {
  const actual = await importOriginal<typeof import("../api/client")>();
  return {
    ...actual,
    getHealth: vi.fn(),
    listJobs: vi.fn(),
  };
});

const mockedGetHealth = vi.mocked(getHealth);
const mockedListJobs = vi.mocked(listJobs);

describe("App shell", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  test("renders the arcade navigation and persistent status strip", async () => {
    mockedGetHealth.mockResolvedValue({ status: "ok" });
    mockedListJobs.mockResolvedValue({
      items: [
        {
          job_id: "job_running",
          kind: "evaluation",
          status: "running",
          config: {},
          result: null,
          error: null,
          log_path: null,
          created_at: "2026-04-27T06:00:00Z",
          started_at: "2026-04-27T06:00:01Z",
          finished_at: null,
          links: { self: "/api/jobs/job_running", logs: "/api/jobs/job_running/logs" },
        },
      ],
    });

    render(
      <MemoryRouter initialEntries={["/"]}>
        <App />
      </MemoryRouter>
    );

    const nav = within(screen.getByRole("navigation", { name: "Primary" }));
    expect(nav.getByRole("link", { name: "Cockpit" })).toHaveAttribute("href", "/");
    expect(nav.getByRole("link", { name: "Play" })).toHaveAttribute("href", "/play");
    expect(nav.getByRole("link", { name: "Train" })).toHaveAttribute("href", "/train");
    expect(nav.getByRole("link", { name: "Evaluate" })).toHaveAttribute("href", "/evaluate");
    expect(nav.getByRole("link", { name: "Artifacts" })).toHaveAttribute("href", "/artifacts");

    await waitFor(() => {
      const status = within(screen.getByRole("status", { name: "Backend status" }));
      expect(status.getByText("API ok")).toBeInTheDocument();
      expect(status.getByText("1 active job")).toBeInTheDocument();
    });
  });
});
