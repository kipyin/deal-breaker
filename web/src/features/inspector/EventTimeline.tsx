import { useMemo, useState } from "react";
import type { InspectorTimelineEvent } from "../../api/types";
import { collectEventTypes, filterTimelineEvents } from "./utils";

type Props = {
  events: InspectorTimelineEvent[] | undefined;
  stepLabel?: string;
};

function formatEventLine(e: InspectorTimelineEvent): string {
  const parts: string[] = [];
  if (e.type) parts.push(e.type);
  if (e.action) parts.push(e.action);
  if (e.player) parts.push(`· ${e.player}`);
  if (e.target) parts.push(`→ ${e.target}`);
  if (e.card) parts.push(`card: ${e.card}`);
  if (e.result) parts.push(`→ ${e.result}`);
  if (e.reason_summary) parts.push(`— ${e.reason_summary}`);
  return parts.length ? parts.join(" ") : JSON.stringify(e);
}

export function EventTimeline({ events, stepLabel }: Props) {
  const [eventType, setEventType] = useState("all");
  const [query, setQuery] = useState("");

  const types = useMemo(() => collectEventTypes(events), [events]);
  const filtered = useMemo(
    () => filterTimelineEvents(events, { eventType, query }),
    [events, eventType, query]
  );
  const total = events?.length ?? 0;

  return (
    <div className="panel event-timeline">
      <h2>Event timeline</h2>
      {stepLabel && <p className="muted" style={{ marginTop: 0 }}>{stepLabel}</p>}
      <div className="event-timeline__filters row" style={{ marginBottom: "0.65rem" }}>
        <label className="event-timeline__filter">
          <span className="muted" style={{ marginRight: "0.35rem" }}>Type</span>
          <select value={eventType} onChange={(e) => setEventType(e.target.value)}>
            <option value="all">All ({total})</option>
            {types.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
        </label>
        <label className="event-timeline__filter" style={{ flex: "1 1 12rem" }}>
          <span className="muted" style={{ marginRight: "0.35rem" }}>Search</span>
          <input
            type="search"
            placeholder="Filter by text…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            style={{ width: "100%", minWidth: 0 }}
          />
        </label>
        <span className="muted">
          Showing {filtered.length} of {total}
        </span>
      </div>
      {total === 0 ? (
        <p className="muted">No events recorded yet.</p>
      ) : filtered.length === 0 ? (
        <p className="muted">No events match the current filters.</p>
      ) : (
        <ol className="event-timeline__list" start={1}>
          {filtered.map((e, i) => {
            const idx = e.index;
            return (
              <li
                key={idx != null ? `ev-${idx}` : `ev-row-${i}-${String(e.type)}-${String(e.turn)}`}
                className="event-timeline__item"
              >
                <span className="event-timeline__index" title={idx != null ? `Event #${idx}` : undefined}>
                  {idx != null ? `#${idx}` : "·"}
                </span>
                <div className="event-timeline__body">
                  <div className="event-timeline__line">{formatEventLine(e)}</div>
                  {e.debug_reasoning && (
                    <details className="event-timeline__debug">
                      <summary>Debug</summary>
                      <pre className="inspector-raw inspector-raw--tight" style={{ maxHeight: 120 }}>
                        {e.debug_reasoning}
                      </pre>
                    </details>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </div>
  );
}
