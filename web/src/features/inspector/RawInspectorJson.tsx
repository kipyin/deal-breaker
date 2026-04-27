import type { JsonObject } from "../../api/types";

type Props = {
  data: JsonObject | null;
  title?: string;
  defaultOpen?: boolean;
};

export function RawInspectorJson({ data, title = "Raw JSON", defaultOpen = false }: Props) {
  return (
    <details className="panel raw-inspector" open={defaultOpen}>
      <summary style={{ cursor: "pointer", fontWeight: 600, color: "#c5c6d2" }}>{title}</summary>
      <pre className="inspector-raw" style={{ marginTop: "0.65rem" }}>
        {data ? JSON.stringify(data, null, 2) : "…"}
      </pre>
    </details>
  );
}
