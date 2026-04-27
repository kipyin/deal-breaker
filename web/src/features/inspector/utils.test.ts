import { describe, expect, test } from "vitest";
import type { InspectorTimelineEvent } from "../../api/types";
import { filterTimelineEvents, collectEventTypes } from "./utils";

const sample: InspectorTimelineEvent[] = [
  { type: "draw", turn: 1, player: "P1", index: 0, reason_summary: "drew two" },
  { type: "play", turn: 1, player: "P1", action: "money", index: 1, reason_summary: "played cash" },
  { type: "draw", turn: 2, player: "P2", index: 2 },
];

describe("filterTimelineEvents", () => {
  test("returns all when type is all and query empty", () => {
    expect(filterTimelineEvents(sample, { eventType: "all", query: "" })).toHaveLength(3);
  });

  test("filters by type", () => {
    expect(
      filterTimelineEvents(sample, { eventType: "draw", query: "" })
    ).toHaveLength(2);
  });

  test("filters by text", () => {
    expect(
      filterTimelineEvents(sample, { eventType: "all", query: "two" })
    ).toHaveLength(1);
  });
});

describe("collectEventTypes", () => {
  test("returns sorted unique types", () => {
    expect(collectEventTypes(sample)).toEqual(["draw", "play"]);
  });
});
