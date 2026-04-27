import type { InspectorCard, InspectorTimelineEvent } from "../../api/types";

export function cardLabel(c: InspectorCard | undefined | null): string {
  if (!c) return "—";
  if (typeof c.name === "string" && c.name) return c.name;
  if (typeof c.id === "string" && c.id) return c.id;
  if (c.kind) return String(c.kind);
  return "Card";
}

export function eventSearchText(e: InspectorTimelineEvent): string {
  const parts = [
    e.type,
    e.player,
    e.action,
    e.target,
    e.card,
    e.result,
    e.reason_summary,
  ];
  return parts
    .filter((x) => x != null && String(x).length > 0)
    .map((x) => String(x).toLowerCase())
    .join(" ");
}

export function filterTimelineEvents(
  events: InspectorTimelineEvent[] | undefined,
  opts: { eventType: string; query: string }
): InspectorTimelineEvent[] {
  if (!events?.length) return [];
  const q = opts.query.trim().toLowerCase();
  return events.filter((e) => {
    if (opts.eventType !== "all" && String(e.type ?? "") !== opts.eventType) {
      return false;
    }
    if (!q) return true;
    return eventSearchText(e).includes(q);
  });
}

export function collectEventTypes(events: InspectorTimelineEvent[] | undefined): string[] {
  if (!events?.length) return [];
  const set = new Set<string>();
  for (const e of events) {
    if (e.type) set.add(String(e.type));
  }
  return Array.from(set).sort();
}
