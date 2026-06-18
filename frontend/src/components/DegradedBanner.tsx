import { useEffect, useState } from "react";
import { Info, X } from "lucide-react";
import type { ToolError } from "../types";

// Map internal tool names to the human-facing capability that degraded.
function friendlyCapabilities(toolErrors: ToolError[]): string[] {
  const caps = new Set<string>();
  for (const e of toolErrors) {
    const t = e.tool.toLowerCase();
    if (t.includes("scoring")) caps.add("scoring");
    else if (t.includes("gap")) caps.add("test generation");
    else if (t.includes("embed") || t.includes("nlp")) caps.add("similarity analysis");
    else caps.add(e.tool.replace(/^llm:/, ""));
  }
  return [...caps];
}

function joinNicely(items: string[]): string {
  if (items.length <= 1) return items[0] ?? "";
  return `${items.slice(0, -1).join(", ")} and ${items[items.length - 1]}`;
}

export default function DegradedBanner({ toolErrors }: { toolErrors: ToolError[] }) {
  const [dismissed, setDismissed] = useState(false);

  // Re-show if a fresh set of errors arrives.
  useEffect(() => {
    if (toolErrors.length) setDismissed(false);
  }, [toolErrors.length]);

  if (!toolErrors.length || dismissed) return null;

  const caps = friendlyCapabilities(toolErrors);
  return (
    <div className="banner banner-info" role="status">
      <Info size={18} />
      <span>
        Running with fallbacks — <span className="banner-strong">{joinNicely(caps)}</span> used a
        deterministic method instead of the LLM. Results may be less precise.
      </span>
      <button className="banner-dismiss" onClick={() => setDismissed(true)} aria-label="Dismiss">
        <X size={16} />
      </button>
    </div>
  );
}
